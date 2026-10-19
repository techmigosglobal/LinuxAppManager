#!/usr/bin/env bash
# Reuse the production portable runtime; no host /usr paths in the Snap launcher.
set -euo pipefail
[[ $# == 4 ]] || { echo 'usage: pack-snap.sh APPIMAGE RUNTIME_REPORT SOURCE_COMMIT OUTPUT_DIR' >&2; exit 2; }
image=$(realpath "$1")
report=$(realpath "$2")
commit="$3"
output=$(realpath -m "$4")
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
for tool in snap unsquashfs patchelf python3 xvfb-run dbus-run-session; do
  command -v "$tool" >/dev/null || { echo "missing Snap packaging dependency: $tool" >&2; exit 1; }
done
[[ -f /snap/core24/current/lib64/ld-linux-x86-64.so.2 ]] || {
  echo 'core24 must be installed to test the actual Snap base loader' >&2; exit 1;
}
work=$(mktemp -d "${TMPDIR:-/tmp}/lam-snap.XXXXXXXX")
trap 'rm -rf "$work"' EXIT
chmod +x "$image"
(cd "$work" && "$image" --appimage-extract >/dev/null)
appdir="$work/squashfs-root"
filename=$(python3 "$root/scripts/prepare-snap.py" "$appdir" "$report" "$commit")
snap pack --check-skeleton "$appdir"
mkdir -p "$output" "$work/home"
snap pack "$appdir" "$work" --filename="$filename"
# Check the packed bytes, not just the staging directory. No system installation.
unsquashfs -no-progress -d "$work/verify" "$work/$filename" >/dev/null
verified="$work/verify"
export SNAP="$verified" SNAP_NAME=vin-linux-app-manager HOME="$work/home"
export XDG_DATA_HOME="$HOME/.local/share"
"$verified/AppRun" --cli list --all --json > "$work/inventory.json"
if "$verified/AppRun" --cli uninstall release-smoke --yes > "$work/mutation.log" 2>&1; then
  echo 'Snap unexpectedly permitted host package changes' >&2; exit 1
fi
grep -q 'disabled in sandboxed builds' "$work/mutation.log"
xvfb-run -a dbus-run-session -- "$verified/AppRun" --appimage-smoke-test
cp "$work/$filename" "$output/"
cp "$verified/usr/share/linux-app-manager/Snap.build.json" "$output/$filename.build.json"
printf 'Verified packed Snap (installation and store approval separate): %s\n' "$output/$filename"
