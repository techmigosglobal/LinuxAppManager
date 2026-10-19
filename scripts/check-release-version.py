#!/usr/bin/env python3
"""Reject inconsistent release versions and mutable/nonrelease refs."""
import argparse
import pathlib
import re
import subprocess
import sys
import tomllib
import xml.etree.ElementTree as ET


def check(root, version=None, tag=None):
    manifest = tomllib.loads((root / "Cargo.toml").read_text())
    actual = manifest["package"]["version"]
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", actual):
        raise ValueError("release version must be a stable semantic version")
    if version is not None and version != actual:
        raise ValueError(f"requested version {version!r} differs from Cargo version {actual}")
    if tag is not None:
        if tag != f"v{actual}":
            raise ValueError(f"release tag must be v{actual}, got {tag!r}")
        subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}"],
                       check=True, capture_output=True, text=True)
        head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", f"refs/tags/{tag}^{{commit}}"], text=True).strip()
        if head != commit:
            raise ValueError("checked out source does not match the release tag")
    lock = tomllib.loads((root / "Cargo.lock").read_text())
    package = next(p for p in lock["package"] if p["name"] == manifest["package"]["name"])
    values = {"Cargo.lock": package["version"]}
    patterns = {
        "debian/changelog": r"\A\S+ \(([^)]+)\)",
        "rpm/linux-app-manager.spec": r"(?m)^Version:\s*(\S+)",
        "snap/snapcraft.yaml": r"(?m)^version:\s*['\"]?([^'\"\s]+)",
    }
    for path, pattern in patterns.items():
        match = re.search(pattern, (root / path).read_text())
        if not match:
            raise ValueError(f"cannot read version from {path}")
        values[path] = match[1].split("-", 1)[0] if path == "debian/changelog" else match[1]
    arch = root / "arch/PKGBUILD"
    if arch.exists():
        match = re.search(r"(?m)^pkgver=['\"]?([^'\"\s]+)", arch.read_text())
        if not match:
            raise ValueError("cannot read Arch recipe version")
        values["arch/PKGBUILD"] = match[1]
    elif not (root / "arch/PKGBUILD.in").is_file():
        raise ValueError("Arch source template is missing")
    metadata = ET.parse(root / "packaging/io.github.techmigosglobal.LinuxAppManager.metainfo.xml")
    release = metadata.find("./releases/release")
    if release is None:
        raise ValueError("AppStream release metadata is missing")
    values["AppStream"] = release.attrib.get("version")
    for path, found in values.items():
        if found != actual:
            raise ValueError(f"{path}: version {found!r} differs from {actual}")
    return actual


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parent.parent)
    parser.add_argument("--version")
    parser.add_argument("--tag")
    args = parser.parse_args()
    try:
        print(check(args.root, args.version, args.tag))
    except (OSError, ValueError, KeyError, StopIteration, subprocess.CalledProcessError) as error:
        print(f"release version check failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
