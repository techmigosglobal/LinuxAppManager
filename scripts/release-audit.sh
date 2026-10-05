#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

failures=0
for required in LICENSE debian/copyright Cargo.toml Cargo.lock README.md packaging/io.github.techmigosglobal.LinuxAppManager.desktop packaging/io.github.techmigosglobal.LinuxAppManager.metainfo.xml packaging/io.github.techmigosglobal.LinuxAppManager.svg packaging/io.github.techmigosglobal.LinuxAppManager.png website/assets/screenshots/applications.png website/assets/screenshots/duplicates.png website/assets/screenshots/history.png; do
  if [[ ! -f "$required" ]]; then
    echo "missing release input: $required" >&2
    failures=$((failures + 1))
  fi
done

if ! python3 - <<'PY'
from pathlib import Path

png_signature = b"\x89PNG\r\n\x1a\n"
if Path("packaging/io.github.techmigosglobal.LinuxAppManager.png").read_bytes()[:8] != png_signature:
    raise SystemExit("release icon is not a PNG image")
print("release PNG icon: valid")
PY
then
  failures=$((failures + 1))
fi

if rg -n -i 'example\.org|linux-app-manager-maintainers@example\.org' \
  README.md Cargo.toml Cargo.lock debian rpm packaging website docs snap arch flatpak; then
  echo "provisional maintainer contact found in release inputs" >&2
  failures=$((failures + 1))
fi

if ! rg -q 'Vin-Linux-App-Manager@techmigos\.com|https://techmigos\.com' \
  debian/control debian/changelog debian/copyright rpm/linux-app-manager.spec \
  packaging/io.github.techmigosglobal.LinuxAppManager.metainfo.xml website/index.html; then
  echo "final maintainer/support contact is missing" >&2
  failures=$((failures + 1))
fi

if rg -n -i "(password|secret|api[_-]?key|token)[[:space:]]*[:=][[:space:]]*[\"']?[A-Za-z0-9_./+-]{12,}" \
  --glob '!target/**' --glob '!Cargo.lock' .; then
  echo "possible credential material found in release inputs" >&2
  failures=$((failures + 1))
fi

if ! python3 - <<'PY'
import xml.etree.ElementTree as ET
ET.parse('packaging/io.github.techmigosglobal.LinuxAppManager.metainfo.xml')
print('AppStream XML: valid')
PY
then
  failures=$((failures + 1))
fi

if ! python3 -m py_compile gui/app.py tests/gui_smoke.py tests/gui_accessibility_smoke.py; then
  failures=$((failures + 1))
fi

if ! ./scripts/verify-website.sh; then
  failures=$((failures + 1))
fi

if ! ./scripts/verify-package-recipes.sh; then
  failures=$((failures + 1))
fi

if (( failures > 0 )); then
  exit 1
fi

echo "release audit inputs: valid"
