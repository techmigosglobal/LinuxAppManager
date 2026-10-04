#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_URL="${LAM_SOURCE_URL:?Set LAM_SOURCE_URL to the tagged source repository URL}"
SOURCE_COMMIT="${LAM_SOURCE_COMMIT:?Set LAM_SOURCE_COMMIT to an immutable release commit}"
OUT_DIR="${1:-$ROOT/dist/flatpak}"

mkdir -p "$OUT_DIR"
if ! command -v flatpak-cargo-generator.py >/dev/null 2>&1; then
  echo "flatpak-cargo-generator.py is required to vendor Cargo dependencies" >&2
  exit 1
fi

flatpak-cargo-generator.py "$ROOT/Cargo.lock" -o "$OUT_DIR/cargo-sources.json"
sed \
  -e "s|@SOURCE_URL@|$SOURCE_URL|g" \
  -e "s|@SOURCE_COMMIT@|$SOURCE_COMMIT|g" \
  "$ROOT/flatpak/io.github.linuxappmanager.Lam.yml.in" > "$OUT_DIR/io.github.linuxappmanager.Lam.yml"
echo "rendered Flatpak manifest in $OUT_DIR"
