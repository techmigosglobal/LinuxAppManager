#!/usr/bin/env python3
"""Build a new signed APT tree from verified release packages, never in place.

Input: PACKAGES/{ubuntu24.04,ubuntu26.04,debian13}/*.deb. Only the newest two
versions per suite are retained. Signing uses the caller's isolated GNUPGHOME.
"""

import argparse
import copy
import functools
import gzip
import hashlib
import io
import json
import lzma
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import xml.etree.ElementTree as ET

SUITES = ("ubuntu24.04", "ubuntu26.04", "debian13")
APP_ID = "io.github.techmigosglobal.LinuxAppManager"
DEFAULT_URL = "https://techmigosglobal.github.io/LinuxAppManager/apt"


def run(*args, **kwargs):
    return subprocess.check_output(args, **kwargs)


def compare_versions(left, right):
    for relation, result in (("lt", -1), ("gt", 1)):
        if subprocess.run(["dpkg", "--compare-versions", left, relation, right]).returncode == 0:
            return result
    return 0


def inspect_package(path):
    if path.is_symlink() or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.+_~%-]*\.deb", path.name):
        raise ValueError(f"unsafe package filename: {path}")
    fields = {
        field: run("dpkg-deb", "--field", str(path), field).decode().strip()
        for field in ("Package", "Version", "Architecture")
    }
    if fields["Package"] != "linux-app-manager" or fields["Architecture"] != "amd64":
        raise ValueError(f"unexpected package or architecture: {path}")
    subprocess.run(["dpkg", "--validate-version", fields["Version"]], check=True)
    return fields


def package_metadata(package):
    """Read only named regular files; never unpack arbitrary archive paths."""
    wanted = {
        f"usr/share/metainfo/{APP_ID}.metainfo.xml": "metadata",
        f"usr/share/icons/hicolor/512x512/apps/{APP_ID}.png": "icon",
    }
    result = {}
    with tempfile.TemporaryFile() as stream:
        subprocess.run(["dpkg-deb", "--fsys-tarfile", str(package)], stdout=stream, check=True)
        stream.seek(0)
        with tarfile.open(fileobj=stream) as archive:
            for member in archive:
                name = member.name.removeprefix("./")
                if name not in wanted:
                    continue
                if not member.isfile() or member.size > 4 * 1024 * 1024:
                    raise ValueError(f"unsafe metadata member: {member.name}")
                result[wanted[name]] = archive.extractfile(member).read()
    if set(result) != {"metadata", "icon"}:
        raise ValueError(f"package lacks AppStream metadata or release icon: {package}")
    component = ET.fromstring(result["metadata"])
    if component.tag != "component" or component.findtext("id") != APP_ID:
        raise ValueError("package has an unexpected AppStream ID")
    return component, result["icon"]


def write_catalog(package, directory):
    from PIL import Image

    component, icon = package_metadata(package)
    collection = ET.Element("components", {"version": "1.0", "origin": "vin-linuxmanager"})
    component = copy.deepcopy(component)
    for node in list(component):
        if node.tag in ("icon", "pkgname"):
            component.remove(node)
    ET.SubElement(component, "pkgname").text = "linux-app-manager"
    for size in (64, 128):
        ET.SubElement(component, "icon", {"type": "cached", "width": str(size), "height": str(size)}).text = f"{APP_ID}.png"
        image = Image.open(io.BytesIO(icon)).convert("RGBA")
        image.thumbnail((size, size))
        resized = io.BytesIO()
        image.save(resized, format="PNG")
        with tarfile.open(directory / f"icons-{size}x{size}.tar.gz", "w:gz") as archive:
            info = tarfile.TarInfo(f"{APP_ID}.png")
            info.size = len(resized.getvalue())
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(resized.getvalue()))
    collection.append(component)
    xml = directory / "Components-amd64.xml"
    ET.ElementTree(collection).write(xml, encoding="utf-8", xml_declaration=True)
    subprocess.run(["appstreamcli", "validate", "--no-net", str(xml)], check=True)
    yaml = directory / "Components-amd64.yml"
    subprocess.run(["appstreamcli", "convert", "--format=yaml", str(xml), str(yaml)], check=True)
    yaml.with_suffix(".yml.gz").write_bytes(gzip.compress(yaml.read_bytes(), mtime=0))
    # Collection XML is useful for independently inspecting generated catalogs.
    xml.with_suffix(".xml.gz").write_bytes(gzip.compress(xml.read_bytes(), mtime=0))
    xml.unlink()
    yaml.unlink()


def sign(path, key_id, clear=False):
    args = ["gpg", "--batch", "--yes", "--local-user", key_id]
    passphrase = os.environ.get("GPG_PASSPHRASE_FILE")
    if passphrase:
        args += ["--pinentry-mode", "loopback", "--passphrase-file", passphrase]
    target = path.with_name("InRelease" if clear else "Release.gpg")
    args += ["--output", str(target), "--clearsign" if clear else "--detach-sign", str(path)]
    subprocess.run(args, check=True)


def build(packages, output, key_id, base_url=DEFAULT_URL):
    if output.exists():
        raise ValueError("output must not exist; compose into a fresh directory")
    if not re.fullmatch(r"[A-Fa-f0-9]{40,64}", key_id):
        raise ValueError("use the complete signing key fingerprint")
    if not base_url.startswith("https://") or any(c.isspace() for c in base_url):
        raise ValueError("repository URL must be HTTPS without whitespace")
    packages, output = packages.resolve(), output.resolve()
    selections = {}
    for suite in SUITES:
        versions = {}
        for package in sorted((packages / suite).glob("*.deb")):
            fields = inspect_package(package)
            version = fields["Version"]
            if suite not in version:
                raise ValueError(f"package version must identify its suite {suite}: {package}")
            digest = hashlib.sha256(package.read_bytes()).hexdigest()
            if version in versions and versions[version][1] != digest:
                raise ValueError(f"different artifacts share version {version}")
            versions[version] = (package, digest)
        ordered = sorted(versions, key=functools.cmp_to_key(compare_versions), reverse=True)[:2]
        if not ordered:
            raise ValueError(f"no packages for required suite {suite}")
        selections[suite] = [(version, *versions[version]) for version in ordered]

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".apt-", dir=output.parent) as work:
        root = Path(work) / "apt"
        root.mkdir()
        public_key = run("gpg", "--batch", "--export", key_id)
        if not public_key:
            raise ValueError("signing key has no exportable public key")
        (root / "vin-linuxmanager.gpg").write_bytes(public_key)
        (root / "key-fingerprint.txt").write_text(key_id.upper() + "\n")
        manifest = {"url": base_url.rstrip("/"), "key_fingerprint": key_id.upper(), "suites": {}}
        for suite, selected in selections.items():
            pool = root / "pool" / suite / "main" / "l" / "linux-app-manager"
            pool.mkdir(parents=True)
            for _, package, _ in selected:
                shutil.copyfile(package, pool / package.name)
            dist = root / "dists" / suite
            binary = dist / "main" / "binary-amd64"
            binary.mkdir(parents=True)
            index = run("apt-ftparchive", "packages", f"pool/{suite}", cwd=root)
            (binary / "Packages").write_bytes(index)
            (binary / "Packages.gz").write_bytes(gzip.compress(index, mtime=0))
            (binary / "Packages.xz").write_bytes(lzma.compress(index))
            catalog = dist / "main" / "dep11"
            catalog.mkdir()
            write_catalog(selected[0][1], catalog)
            indexed = list(dist.rglob("*"))
            for path in indexed:
                if path.is_file():
                    hashed = path.parent / "by-hash" / "SHA256" / hashlib.sha256(path.read_bytes()).hexdigest()
                    hashed.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(path, hashed)
            options = {
                "Origin": "VIN-LinuxManager", "Label": "VIN-LinuxManager",
                "Suite": suite, "Codename": suite, "Architectures": "amd64",
                "Components": "main", "Acquire-By-Hash": "yes",
                "Description": "VIN-LinuxManager native packages",
            }
            args = ["apt-ftparchive"]
            for name, value in options.items():
                args += ["-o", f"APT::FTPArchive::Release::{name}={value}"]
            release = run(*args, "release", f"dists/{suite}", cwd=root)
            (dist / "Release").write_bytes(release)
            sign(dist / "Release", key_id)
            sign(dist / "Release", key_id, clear=True)
            subprocess.run(["gpg", "--batch", "--verify", str(dist / "InRelease")], check=True)
            manifest["suites"][suite] = [{"version": v, "filename": p.name, "sha256": h} for v, p, h in selected]
            (root / f"vin-linuxmanager-{suite}.sources").write_text(
                f"Types: deb\nURIs: {base_url.rstrip('/')}\nSuites: {suite}\nComponents: main\n"
                "Architectures: amd64\nSigned-By: /etc/apt/keyrings/vin-linuxmanager.gpg\n"
            )
        (root / "repository.json").write_text(json.dumps(manifest, indent=2) + "\n")
        root.rename(output)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packages", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--key-id", required=True)
    parser.add_argument("--base-url", default=DEFAULT_URL)
    args = parser.parse_args()
    build(args.packages, args.output, args.key_id, args.base_url)


if __name__ == "__main__":
    main()
