#!/usr/bin/env bash
set -euo pipefail
[[ $# -eq 2 ]] || { echo "usage: $0 SOURCE_DIRECTORY OUTPUT_DIRECTORY" >&2; exit 2; }
source_dir=$(realpath "$1")
mkdir -p "$2"
output_dir=$(realpath "$2")
[[ $(uname -m) == x86_64 ]] || { echo "AppImage currently supports x86_64 only" >&2; exit 1; }
# A newer glibc builder silently raises the minimum supported OS.
. /etc/os-release
if [[ "$ID" != ubuntu || "$VERSION_ID" != 24.04 ]]; then
  [[ ${LAM_APPIMAGE_ALLOW_UNSUPPORTED_BUILDER:-} == 1 ]] || {
    echo "Production AppImages must be built on Ubuntu 24.04; override only for development smoke tests" >&2
    exit 1
  }
fi
for command in cargo curl sha256sum desktop-file-validate appstreamcli xvfb-run dbus-run-session; do
  command -v "$command" >/dev/null || { echo "missing build dependency: $command" >&2; exit 1; }
done
version=$(/usr/bin/python3 -c 'import pathlib,sys,tomllib; print(tomllib.loads(pathlib.Path(sys.argv[1]).read_text())["package"]["version"])' "$source_dir/Cargo.toml")
work=$(mktemp -d "${TMPDIR:-/tmp}/vin-appimage.XXXXXXXX")
trap 'rm -rf "$work"' EXIT
appdir="$work/AppDir"
mkdir -p "$appdir"
# External caches can be moved out of the checkout and onto a capacious filesystem.
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-$work/cargo-target}"
export CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-1}"
(cd "$source_dir" && cargo build --offline --locked --release)
/usr/bin/python3 "$source_dir/packaging/appimage/bundle.py" "$source_dir" "$appdir" "$CARGO_TARGET_DIR/release/lam"
desktop-file-validate "$appdir/io.github.techmigosglobal.LinuxAppManager.desktop"
appstreamcli validate --no-net "$appdir/usr/share/metainfo/io.github.techmigosglobal.LinuxAppManager.appdata.xml"
/usr/bin/python3 - "$source_dir/packaging/appimage/tools.json" "$work" <<'PY'
import hashlib, json, pathlib, sys, urllib.request
pins = json.loads(pathlib.Path(sys.argv[1]).read_text())
for name, pin in pins.items():
    path = pathlib.Path(sys.argv[2]) / name
    request = urllib.request.Request(pin["url"], headers={"User-Agent": "VIN-LinuxManager-release-builder"})
    with urllib.request.urlopen(request, timeout=120) as response, path.open("wb") as output:
        while block := response.read(1024 * 1024):
            output.write(block)
    if hashlib.file_digest(path.open("rb"), "sha256").hexdigest() != pin["sha256"]:
        raise SystemExit(f"checksum mismatch for {name}")
    path.chmod(0o755)
PY
# Extracting the build tool and the produced artifact never requires FUSE.
(cd "$work" && ./appimagetool --appimage-extract >/dev/null)
artifact="$work/VIN-LinuxManager-${version}-x86_64.AppImage"
ARCH=x86_64 "$work/squashfs-root/AppRun" --runtime-file "$work/runtime" "$appdir" "$artifact"
mkdir "$work/verify"
(cd "$work/verify" && "$artifact" --appimage-extract >/dev/null)
verified="$work/verify/squashfs-root"
mkdir -p "$work/home" "$work/runtime-dir"
chmod 700 "$work/runtime-dir"
HOME="$work/home" XDG_DATA_HOME="$work/home/.local/share" \
  "$verified/AppRun" --cli providers --json > "$work/providers.json"
/usr/bin/python3 - "$work/providers.json" <<'PY'
import json, pathlib, sys
providers = json.loads(pathlib.Path(sys.argv[1]).read_text())
assert any(provider["source"] == "app_image" for provider in providers)
PY
HOME="$work/home" XDG_DATA_HOME="$work/home/.local/share" XDG_RUNTIME_DIR="$work/runtime-dir" \
  xvfb-run -a dbus-run-session -- "$verified/AppRun" --appimage-smoke-test
# Expose only artifacts which passed extraction and bundled GUI verification.
cp "$artifact" "$output_dir/"
cp "$appdir/usr/share/linux-app-manager/AppImage.build.json" \
  "$output_dir/VIN-LinuxManager-${version}-x86_64.AppImage.build.json"
echo "Verified AppImage: $output_dir/$(basename "$artifact")"
