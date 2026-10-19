#!/usr/bin/env python3
"""Download the two newest complete, signed native releases for Pages.

Trust is rooted in a public key committed to the source repository, never a key
downloaded beside an untrusted package. Legacy releases without distro suites
are left untouched and are not used to seed an incompatible suite.
"""

import argparse
import functools
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

SUITES = ("ubuntu24.04", "ubuntu26.04", "debian13")


def release_compare(left, right):
    for relation, result in (("lt", -1), ("gt", 1)):
        if subprocess.run(["dpkg", "--compare-versions", left["tag_name"][1:], relation,
                           right["tag_name"][1:]]).returncode == 0:
            return result
    return 0


def eligible_releases(releases):
    selected = []
    for release in releases:
        if release["draft"] or release["prerelease"] or not re.fullmatch(r"v\d+\.\d+\.\d+", release["tag_name"]):
            continue
        assets = {asset["name"] for asset in release["assets"]}
        packages = [name for name in assets if name.endswith(".deb")]
        if not all(any(suite in name for name in packages) for suite in SUITES):
            continue
        if not {"SHA256SUMS", "SHA256SUMS.asc"}.issubset(assets):
            raise ValueError(f"native release lacks signed checksums: {release['tag_name']}")
        if not all(name + ".asc" in assets for name in packages):
            raise ValueError(f"native release lacks package signatures: {release['tag_name']}")
        selected.append(release)
    return sorted(selected, key=functools.cmp_to_key(release_compare), reverse=True)[:2]


def verify_download(directory, keyring):
    subprocess.run(["gpgv", "--keyring", str(keyring), str(directory / "SHA256SUMS.asc"),
                    str(directory / "SHA256SUMS")], check=True)
    sums = {}
    for line in (directory / "SHA256SUMS").read_text().splitlines():
        digest, filename = line.split(maxsplit=1)
        filename = filename.removeprefix("*")
        if not re.fullmatch(r"[0-9a-f]{64}", digest) or Path(filename).name != filename:
            raise ValueError("release checksums must use safe relative basenames")
        if filename in sums:
            raise ValueError("duplicate checksum entry")
        sums[filename] = digest
    for package in directory.glob("*.deb"):
        if package.is_symlink() or package.name not in sums:
            raise ValueError(f"unsigned or unsafe package: {package.name}")
        if hashlib.sha256(package.read_bytes()).hexdigest() != sums[package.name]:
            raise ValueError(f"checksum mismatch: {package.name}")
        subprocess.run(["gpgv", "--keyring", str(keyring), str(package) + ".asc", str(package)], check=True)


def collect(repository, public_key, output):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("invalid GitHub repository")
    if output.exists():
        raise ValueError("package output must be a new directory")
    releases = json.loads(subprocess.check_output([
        "gh", "api", "--paginate", "--slurp", f"repos/{repository}/releases?per_page=100"
    ]))
    selected = eligible_releases([release for page in releases for release in page])
    if not selected:
        raise ValueError("no complete signed multi-suite native release is public; preserving existing Pages deployment")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lam-release-download-") as work:
        work = Path(work)
        keyring = work / "trusted.gpg"
        subprocess.run(["gpg", "--batch", "--dearmor", "--output", str(keyring), str(public_key)], check=True)
        stage = work / "packages"
        for suite in SUITES:
            (stage / suite).mkdir(parents=True)
        for release in selected:
            download = work / release["tag_name"]
            download.mkdir()
            subprocess.run([
                "gh", "release", "download", release["tag_name"], "--repo", repository,
                "--dir", str(download), "--pattern", "*.deb", "--pattern", "*.deb.asc",
                "--pattern", "SHA256SUMS", "--pattern", "SHA256SUMS.asc",
            ], check=True)
            verify_download(download, keyring)
            for package in download.glob("*.deb"):
                suites = [suite for suite in SUITES if suite in package.name]
                if len(suites) != 1:
                    raise ValueError(f"package has no unambiguous suite: {package.name}")
                target = stage / suites[0] / package.name
                if target.exists() and target.read_bytes() != package.read_bytes():
                    raise ValueError("different releases contain conflicting artifacts")
                shutil.copyfile(package, target)
        shutil.copytree(stage, output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default="techmigosglobal/LinuxAppManager")
    parser.add_argument("--public-key", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    collect(args.repository, args.public_key, args.output)
