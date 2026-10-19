#!/usr/bin/env python3
"""Copy exact vendored license notices and deterministic Cargo attribution metadata."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import tomllib

NOTICE_PREFIXES = ("LICENSE", "LICENCE", "COPYING", "NOTICE", "COPYRIGHT", "UNLICENSE")
# Only an explicit public-domain declaration may omit a license text. SPDX
# waivers such as CC0 and Unlicense still need their actual upstream text.
PUBLIC_DOMAIN = {"LicenseRef-Public-Domain", "Public-Domain", "public-domain"}


def collect(source: Path) -> Path:
    source = source.resolve()
    vendor = source / "vendor"
    if not vendor.is_dir():
        raise ValueError("source must contain vendor/")
    crates = sorted(path for path in vendor.iterdir() if path.is_dir())
    if not crates:
        raise ValueError("vendor/ contains no dependencies")
    records = []
    copies = []
    for crate in crates:
        if crate.is_symlink():
            raise ValueError(f"vendored dependency is a symlink: {crate.name}")
        manifest = crate / "Cargo.toml"
        if not manifest.is_file() or manifest.is_symlink():
            raise ValueError(f"vendored dependency is missing Cargo.toml: {crate.name}")
        package = tomllib.loads(manifest.read_text())["package"]
        name, version = package.get("name"), package.get("version")
        license_id, license_file = package.get("license"), package.get("license-file")
        if not isinstance(name, str) or not isinstance(version, str):
            raise ValueError(f"dependency has invalid name/version: {crate.name}")
        if license_id is not None and not isinstance(license_id, str):
            raise ValueError(f"dependency has invalid Cargo license metadata: {crate.name}")
        if license_file is not None and not isinstance(license_file, str):
            raise ValueError(f"dependency has invalid Cargo license-file metadata: {crate.name}")
        authors = package.get("authors", [])
        if not isinstance(authors, list) or not all(isinstance(author, str) for author in authors):
            raise ValueError(f"dependency has invalid Cargo authors metadata: {crate.name}")
        if not license_id and not license_file:
            raise ValueError(f"dependency has no Cargo license declaration: {crate.name}")
        notices = {path for path in crate.rglob("*") if path.is_file() and path.name.upper().startswith(NOTICE_PREFIXES)}
        if license_file:
            declared = crate / license_file
            if not declared.resolve().is_relative_to(crate.resolve()) or not declared.is_file():
                raise ValueError(f"invalid or missing license-file: {crate.name}/{license_file}")
            notices.add(declared)
        # A NOTICE or COPYRIGHT alone is attribution, not the license grant.
        license_texts = [path for path in notices if path.name.upper().startswith(("LICENSE", "LICENCE", "COPYING", "UNLICENSE")) or path == (crate / license_file if license_file else None)]
        if not license_texts and license_id not in PUBLIC_DOMAIN:
            raise ValueError(f"dependency has no upstream license text: {crate.name} ({license_id})")
        file_records = []
        for notice in sorted(notices):
            if notice.is_symlink() or not notice.resolve().is_relative_to(crate.resolve()):
                raise ValueError(f"unsafe license notice: {notice}")
            relative = notice.relative_to(crate)
            data = notice.read_bytes()
            if not data.strip():
                raise ValueError(f"empty upstream license notice: {crate.name}/{relative}")
            copies.append((Path(crate.name) / relative, data))
            file_records.append({"path": relative.as_posix(), "sha256": hashlib.sha256(data).hexdigest()})
        records.append({"directory": crate.name, "name": name, "version": version,
                        "license": license_id, "license_file": license_file,
                        "authors": authors, "files": file_records})
    output = source / "THIRD_PARTY_LICENSES"
    if output.is_symlink():
        raise ValueError("THIRD_PARTY_LICENSES cannot be a symlink")
    with tempfile.TemporaryDirectory(prefix=".lam-licenses-", dir=source) as temporary:
        staging = Path(temporary) / "THIRD_PARTY_LICENSES"
        staging.mkdir()
        for relative, data in copies:
            path = staging / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (staging / "inventory.json").write_text(json.dumps({"format": "vendored-cargo-license-inventory-v1", "packages": records}, sort_keys=True, indent=2) + "\n")
        if output.exists():
            if not (output / "inventory.json").is_file():
                raise ValueError("refusing to replace unrecognized THIRD_PARTY_LICENSES directory")
            shutil.rmtree(output)
        shutil.move(staging, output)
    return output


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: collect-vendor-licenses.py SOURCE_ROOT")
    try:
        output = collect(Path(sys.argv[1]))
        print(f"Collected exact vendored license notices: {output}")
    except (OSError, ValueError, KeyError, tomllib.TOMLDecodeError) as error:
        sys.exit(str(error))
