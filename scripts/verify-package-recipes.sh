#!/usr/bin/env bash
# Recipe syntax/metadata validation; this is not a clean package build.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
for required in rpmspec desktop-file-validate appstreamcli python3; do
  command -v "$required" >/dev/null || { echo "required recipe validator unavailable: $required" >&2; exit 1; }
done
rpmspec --parse rpm/linux-app-manager.spec >/dev/null
desktop-file-validate packaging/io.github.techmigosglobal.LinuxAppManager.desktop
appstreamcli validate --no-net packaging/io.github.techmigosglobal.LinuxAppManager.metainfo.xml
python3 -m unittest discover -s tests -p test_native_packaging.py
if [[ $# == 1 ]]; then
  output="$(mktemp -d "${TMPDIR:-/tmp}/lam-aur-check.XXXXXX")"
  trap 'rm -rf "$output"' EXIT
  scripts/render-aur.py "$1" "$output"
elif [[ $# != 0 ]]; then
  echo 'usage: verify-package-recipes.sh [SOURCE_ARCHIVE]' >&2
  exit 2
fi
echo 'Native recipe syntax and metadata validation: passed'
echo 'Actual clean builds and desktop installation remain separate release gates.'
