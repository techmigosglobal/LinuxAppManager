#!/usr/bin/env python3
"""Keep signed download names identical to GitHub's hosted asset names."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def asset_name(name):
    if Path(name).name != name or "\\" in name:
        raise ValueError("release assets must be flat basenames")
    # Debian versions retain '~' internally; GitHub changes it in upload names.
    result = name.replace("~", ".")
    if not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9._-]*[A-Za-z0-9_-]", result):
        raise ValueError(f"unsupported GitHub asset name: {name}")
    return result


def prepare(directory):
    paths = list(directory.iterdir())
    names = [asset_name(path.name) for path in paths]
    if len(names) != len(set(names)):
        raise ValueError("GitHub asset filename collision")
    if any(path.is_symlink() or not path.is_file() for path in paths):
        raise ValueError("release assets must be ordinary files")
    if (directory / "SHA256SUMS").exists():
        raise ValueError("normalize filenames before signing")
    for path, name in zip(paths, names):
        if path.name != name:
            path.rename(directory / name)


def check_hosted(directory, release):
    if not release["draft"]:
        raise ValueError("installation acceptance requires a draft")
    local = {path.name: path for path in directory.iterdir()}
    hosted = {asset["name"]: asset for asset in release["assets"]}
    if len(hosted) != len(release["assets"]) or set(local) != set(hosted):
        raise ValueError("hosted asset names differ from signed download directory")
    for name, path in local.items():
        asset = hosted[name]
        if path.is_symlink() or not path.is_file() or asset["size"] != path.stat().st_size:
            raise ValueError(f"hosted asset size mismatch: {name}")
        if asset.get("digest") and asset["digest"] != "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError(f"hosted asset digest mismatch: {name}")


def repair(directory, keyring, tag, commit):
    """Verify original signed bytes, then rewrite only download-name metadata.

    The caller must sign the two changed metadata files and verify the entire
    directory before replacing those four assets on the still-private draft.
    """
    def verify(path):
        subprocess.run(["gpgv", "--keyring", str(keyring), str(path) + ".asc", str(path)], check=True)

    verify(directory / "SHA256SUMS")
    verify(directory / "MANIFEST.json")
    manifest_path = directory / "MANIFEST.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest["tag"] != tag or manifest["version"] != tag.removeprefix("v") or manifest["commit"] != commit:
        raise ValueError("draft source identity differs from the immutable tag")
    checksums = {}
    for line in (directory / "SHA256SUMS").read_text().splitlines():
        if not re.fullmatch(r"[0-9a-f]{64}  .+", line):
            raise ValueError("invalid checksum entry")
        name = line[66:]
        asset_name(name)
        if name in checksums:
            raise ValueError("duplicate checksum entry")
        checksums[name] = line[:64]
    entries = manifest["artifacts"]
    original_names = [entry["path"] for entry in entries]
    names = [asset_name(name) for name in original_names]
    if len(names) != len(set(names)) or len(original_names) != len(set(original_names)):
        raise ValueError("GitHub asset filename collision")
    if set(checksums) != set(original_names) | {"MANIFEST.json"}:
        raise ValueError("signed manifest and checksums disagree")
    if checksums["MANIFEST.json"] != hashlib.sha256(manifest_path.read_bytes()).hexdigest():
        raise ValueError("signed manifest checksum mismatch")
    expected = {"MANIFEST.json", "MANIFEST.json.asc", "SHA256SUMS", "SHA256SUMS.asc"}
    for entry, name in zip(entries, names):
        path = directory / name
        expected.update((name, name + ".asc"))
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"missing ordinary asset: {name}")
        if (entry["sha256"] != checksums[entry["path"]]
                or entry["sha256"] != hashlib.sha256(path.read_bytes()).hexdigest()
                or entry["bytes"] != path.stat().st_size):
            raise ValueError(f"original signed bytes changed: {name}")
        verify(path)
    if {path.name for path in directory.iterdir()} != expected:
        raise ValueError("draft contains missing or unexpected assets")
    changed = sum(old != new for old, new in zip(original_names, names))
    if not changed:
        raise ValueError("draft needs no filename metadata repair")
    # No file is modified until every original signature and byte count passed.
    for entry, name in zip(entries, names):
        entry["path"] = name
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    sums = {entry["path"]: entry["sha256"] for entry in entries}
    sums["MANIFEST.json"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    (directory / "SHA256SUMS").write_text("".join(f"{digest}  {name}\n" for name, digest in sorted(sums.items())))
    return changed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "check-hosted", "repair"))
    parser.add_argument("directory", type=Path)
    parser.add_argument("--release-json", type=Path)
    parser.add_argument("--keyring", type=Path)
    parser.add_argument("--tag")
    parser.add_argument("--commit")
    args = parser.parse_args()
    if args.mode == "prepare":
        prepare(args.directory)
    elif args.mode == "check-hosted":
        check_hosted(args.directory, json.loads(args.release_json.read_text()))
    else:
        print("Verified and normalized metadata paths:", repair(args.directory, args.keyring, args.tag, args.commit))
