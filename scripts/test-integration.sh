#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RUSTUP_TOOLCHAIN="${RUSTUP_TOOLCHAIN:-1.90.0}" cargo test --all-targets
python3 -m py_compile gui/app.py tests/gui_smoke.py tests/gui_accessibility_smoke.py

if command -v xvfb-run >/dev/null 2>&1; then
  xvfb-run -a python3 tests/gui_smoke.py
  xvfb-run -a python3 tests/gui_accessibility_smoke.py
else
  echo "xvfb-run is unavailable; GUI smoke test skipped" >&2
fi
