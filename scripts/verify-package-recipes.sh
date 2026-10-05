#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

failures=0

if command -v rpmspec >/dev/null 2>&1; then
  rpmspec --parse rpm/linux-app-manager.spec >/dev/null
  echo "RPM spec: valid"
else
  echo "RPM spec: skipped (rpmspec unavailable)"
fi

if command -v makepkg >/dev/null 2>&1; then
  (cd arch && makepkg --printsrcinfo --packagelist -p PKGBUILD >/dev/null)
  echo "Arch PKGBUILD: valid"
else
  echo "Arch PKGBUILD: skipped (makepkg unavailable)"
fi

if command -v desktop-file-validate >/dev/null 2>&1; then
  desktop-file-validate packaging/io.github.techmigosglobal.LinuxAppManager.desktop
  echo "desktop entry: valid"
else
  echo "desktop entry: skipped (desktop-file-validate unavailable)"
fi

if command -v appstreamcli >/dev/null 2>&1; then
  appstreamcli validate --no-net packaging/io.github.techmigosglobal.LinuxAppManager.metainfo.xml
  echo "AppStream metadata: valid"
else
  echo "AppStream metadata: skipped (appstreamcli unavailable)"
fi

if command -v snapcraft >/dev/null 2>&1; then
  snapcraft lint snap/snapcraft.yaml
  echo "Snap manifest: valid"
else
  echo "Snap manifest: skipped (snapcraft unavailable)"
fi

if command -v flatpak-builder >/dev/null 2>&1; then
  echo "Flatpak manifest: render with scripts/render-flatpak.sh before builder validation"
else
  echo "Flatpak manifest: skipped (flatpak-builder unavailable)"
fi

if (( failures > 0 )); then
  exit 1
fi
