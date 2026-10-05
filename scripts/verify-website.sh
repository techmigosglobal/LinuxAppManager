#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 - <<'PY'
from pathlib import Path

root = Path('website')
required = [
    root / 'index.html',
    root / 'styles.css',
    root / 'script.js',
    root / 'README.md',
    root / 'assets' / 'vin-linuxmanager-mark.svg',
    root / 'assets' / 'vin-linuxmanager-mark.png',
    root / 'assets' / 'screenshots' / 'applications.png',
    root / 'assets' / 'screenshots' / 'duplicates.png',
    root / 'assets' / 'screenshots' / 'history.png',
]
missing = [str(path) for path in required if not path.is_file()]
if missing:
    raise SystemExit(f'missing website files: {missing}')

html = (root / 'index.html').read_text()
for needle in ('<title>VIN-LinuxManager', 'id="main-content"', 'href="styles.css"', 'src="script.js"'):
    if needle not in html:
        raise SystemExit(f'website is missing expected marker: {needle}')

if 'example.org' in html:
    raise SystemExit('website contains a placeholder contact address')

print('website assets: valid')
PY
