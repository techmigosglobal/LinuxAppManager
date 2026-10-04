#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

failures=0
for required in Cargo.toml Cargo.lock README.md packaging/io.github.linuxappmanager.Lam.desktop packaging/io.github.linuxappmanager.Lam.metainfo.xml packaging/io.github.linuxappmanager.Lam.svg; do
  if [[ ! -f "$required" ]]; then
    echo "missing release input: $required" >&2
    failures=$((failures + 1))
  fi
done

if rg -n -i "(password|secret|api[_-]?key|token)[[:space:]]*[:=][[:space:]]*[\"']?[A-Za-z0-9_./+-]{12,}" \
  --glob '!target/**' --glob '!Cargo.lock' .; then
  echo "possible credential material found in release inputs" >&2
  failures=$((failures + 1))
fi

if ! python3 - <<'PY'
import xml.etree.ElementTree as ET
ET.parse('packaging/io.github.linuxappmanager.Lam.metainfo.xml')
print('AppStream XML: valid')
PY
then
  failures=$((failures + 1))
fi

if ! python3 -m py_compile gui/app.py tests/gui_smoke.py tests/gui_accessibility_smoke.py; then
  failures=$((failures + 1))
fi

if ! ./scripts/verify-package-recipes.sh; then
  failures=$((failures + 1))
fi

if (( failures > 0 )); then
  exit 1
fi

echo "release audit inputs: valid"
