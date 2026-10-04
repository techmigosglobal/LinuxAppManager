#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ARTIFACT_DIR="${1:?Usage: write-release-manifest.sh ARTIFACT_DIR [OUTPUT_DIR]}"
OUTPUT_DIR="${2:-$ARTIFACT_DIR}"

mkdir -p "$OUTPUT_DIR"
checksum_file="$OUTPUT_DIR/SHA256SUMS"
manifest_file="$OUTPUT_DIR/MANIFEST.json"
sbom_file="$OUTPUT_DIR/SBOM.cargo.json"

find "$ARTIFACT_DIR" -type f \
  ! -path "$OUTPUT_DIR/SHA256SUMS" \
  ! -path "$OUTPUT_DIR/MANIFEST.json" \
  ! -path "$OUTPUT_DIR/SBOM.cargo.json" \
  -printf '%P\n' | sort | while IFS= read -r relative; do
  (cd "$ARTIFACT_DIR" && sha256sum "$relative")
done > "$checksum_file"

(cd "$ROOT" && cargo metadata --locked --format-version 1) > "$sbom_file"

python3 - "$ARTIFACT_DIR" "$checksum_file" "$manifest_file" <<'PY'
import hashlib
import json
import pathlib
import sys

artifact_dir = pathlib.Path(sys.argv[1])
checksum_file = pathlib.Path(sys.argv[2])
manifest_file = pathlib.Path(sys.argv[3])
entries = []
for line in checksum_file.read_text().splitlines():
    digest, relative = line.split(maxsplit=1)
    path = artifact_dir / relative
    entries.append({
        "path": relative,
        "bytes": path.stat().st_size,
        "sha256": digest,
    })
manifest_file.write_text(json.dumps({"artifacts": entries}, indent=2) + "\n")
PY

echo "wrote $checksum_file"
echo "wrote $manifest_file"
echo "wrote $sbom_file"
