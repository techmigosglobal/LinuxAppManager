#!/usr/bin/env bash
set -euo pipefail
if [[ $# == 2 && "$1" == --artifact ]]; then
  package="$(realpath "$2")"
  [[ "$(dpkg-deb --field "$package" Package)" == linux-app-manager ]] || { echo 'unexpected package name' >&2; exit 1; }
  [[ "$(dpkg-deb --field "$package" Architecture)" == amd64 ]] || { echo 'unexpected package architecture' >&2; exit 1; }
  contents="$(dpkg-deb --contents "$package")"
  for required in \
    './usr/bin/linux-app-manager' \
    './usr/lib/linux-app-manager/lam' \
    './usr/lib/linux-app-manager/app.py' \
    './usr/share/applications/io.github.techmigosglobal.LinuxAppManager.desktop' \
    './usr/share/metainfo/io.github.techmigosglobal.LinuxAppManager.metainfo.xml' \
    './usr/share/icons/hicolor/scalable/apps/io.github.techmigosglobal.LinuxAppManager.svg' \
    './usr/share/icons/hicolor/512x512/apps/io.github.techmigosglobal.LinuxAppManager.png' \
    './usr/share/doc/linux-app-manager/copyright' \
    './usr/share/doc/linux-app-manager/LICENSE' \
    './usr/share/doc/linux-app-manager/THIRD_PARTY_LICENSES/inventory.json'; do
    grep -Fq "$required" <<<"$contents" || { echo "package missing $required" >&2; exit 1; }
  done
  if grep -Eq '(^|/)(target|\.git|__pycache__)(/|$)|(^|/)(\.env|.*\.pem|.*\.key)$' <<<"$contents"; then
    echo "package contains a build/cache/secret path: $package" >&2
    exit 1
  fi
  dependencies="$(dpkg-deb --field "$package" Depends)"
  for required in python3 python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 pkexec; do
    grep -Fq "$required" <<<"$dependencies" || { echo "package dependency missing: $required" >&2; exit 1; }
  done
  dpkg-deb --field "$package" Package Version Architecture
  echo 'Debian artifact content verification: passed (installation not tested)'
  exit 0
fi
if [[ $# != 3 ]]; then
  echo 'usage: verify-clean-debian.sh TARGET SOURCE_ARCHIVE OUTPUT_DIR' >&2
  echo '       verify-clean-debian.sh --artifact PACKAGE.deb' >&2
  echo 'Run build verification inside a matching clean builder; no checks are silently skipped.' >&2
  exit 2
fi
case "$1" in ubuntu24.04|ubuntu26.04|debian13) ;; *) echo 'unsupported Debian target' >&2; exit 2 ;; esac
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$ROOT/scripts/build-native.sh" "$@"
