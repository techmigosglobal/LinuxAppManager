#!/usr/bin/env bash
# Checksums are relative to the artifact directory so downloads remain verifiable.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ARTIFACT_DIR="${1:?Usage: write-release-manifest.sh ARTIFACT_DIR [OUTPUT_DIR]}"
OUTPUT_DIR="${2:-$ARTIFACT_DIR}"
python3 - "$ROOT" "$ARTIFACT_DIR" "$OUTPUT_DIR" <<'PY'
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tomllib

root, artifacts, output = map(pathlib.Path, sys.argv[1:])
artifacts, output = artifacts.resolve(), output.resolve()
if not artifacts.is_dir():
    raise SystemExit("artifact directory does not exist")
output.mkdir(parents=True, exist_ok=True)
if output != artifacts:
    raise SystemExit("OUTPUT_DIR must equal ARTIFACT_DIR; publish one self-contained download directory")
lock = tomllib.loads((root / "Cargo.lock").read_text())
version = tomllib.loads((root / "Cargo.toml").read_text())["package"]["version"]
# This is a locked dependency inventory, not a standards-compliant SPDX/CycloneDX SBOM.
(output / "SBOM.cargo.json").write_text(json.dumps({
    "format": "cargo-lock-dependency-inventory-v1", "version": version,
    "packages": lock["package"],
}, sort_keys=True, indent=2) + "\n")
try:
    commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
except subprocess.CalledProcessError:
    commit = None
entries = []
for path in sorted(artifacts.rglob("*")):
    if path.is_symlink():
        raise SystemExit(f"symlinks are not release artifacts: {path}")
    if not path.is_file() or path.name in {"SHA256SUMS", "MANIFEST.json"}:
        continue
    if path.suffix in {".asc", ".sig"} and path.name != "vin-linuxmanager-release-public-key.asc":
        continue
    relative = path.relative_to(artifacts).as_posix()
    if any(c in relative for c in "\n\r\\"):
        raise SystemExit("release artifact paths cannot contain newlines or backslashes")
    entries.append({"path": relative, "bytes": path.stat().st_size,
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
if not any(e["path"] != "SBOM.cargo.json" for e in entries):
    raise SystemExit("no release artifacts found")
(output / "MANIFEST.json").write_text(json.dumps({
    "version": version, "commit": commit,
    "tag": os.environ.get("RELEASE_TAG"),
    "artifacts": entries,
}, sort_keys=True, indent=2) + "\n")
checksums = [f'{e["sha256"]}  {e["path"]}\n' for e in entries]
checksums.append(f'{hashlib.sha256((output / "MANIFEST.json").read_bytes()).hexdigest()}  MANIFEST.json\n')
(output / "SHA256SUMS").write_text("".join(sorted(checksums, key=lambda line: line.split("  ", 1)[1])))
print(f"wrote release manifest, dependency inventory, and relative checksums to {output}")
PY
