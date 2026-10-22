#!/usr/bin/env bash
# This script installs/removes packages ONLY inside a fresh release-test container.
set -euo pipefail
[[ $# == 2 && -f /.dockerenv && ${LAM_DISPOSABLE_BUILDER:-} == 1 ]] || {
  echo 'smoke-native.sh TARGET PACKAGES requires an explicitly disposable Docker container' >&2
  exit 2
}
build_target="$1"
packages=$(realpath "$2")
script_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
export HOME=/tmp/lam-installed-home
export XDG_RUNTIME_DIR=/tmp/lam-installed-runtime
mkdir -p "$HOME" "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"
case "$build_target" in
  ubuntu*|debian*)
    expected=apt
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y dbus-x11 xvfb "$packages"/linux-app-manager_*"$build_target"*_amd64.deb
    ;;
  fedora*)
    expected=dnf
    dnf install -y dbus-daemon xorg-x11-server-Xvfb python3-gobject "$packages"/linux-app-manager-[0-9]*.x86_64.rpm
    ;;
  arch)
    expected=pacman
    pacman -Syu --noconfirm --needed dbus xorg-server-xvfb python-gobject
    pacman -U --noconfirm "$packages"/*.pkg.tar.zst
    ;;
  *) echo 'unsupported native smoke target' >&2; exit 2 ;;
esac
lam=/usr/lib/linux-app-manager/lam
"$lam" list --all --json > /tmp/native-inventory.json
"$lam" history --json > /tmp/native-history.json
# Both UI and CLI must retain the existing sandbox boundary.
for sandbox in FLATPAK_ID SNAP; do
  if env "$sandbox=release.smoke" "$lam" uninstall release-smoke --yes > /tmp/sandbox-result 2>&1; then
    echo 'sandbox unexpectedly permitted a host operation' >&2; exit 1
  fi
  grep -q 'disabled in sandboxed builds' /tmp/sandbox-result
done
# The absent confirmation must fail before resolving a package or authorizing.
if "$lam" uninstall release-smoke > /tmp/confirmation-result 2>&1; then
  echo 'unconfirmed host operation unexpectedly succeeded' >&2; exit 1
fi
grep -q 'requires explicit confirmation' /tmp/confirmation-result
# Fedora/Arch do not ship the xvfb-run convenience script everywhere.
Xvfb :99 -screen 0 1280x800x24 -nolisten tcp > /tmp/lam-xvfb.log 2>&1 &
display_pid=$!
trap 'kill "$display_pid" 2>/dev/null || true' EXIT
export DISPLAY=:99
for attempt in $(seq 1 50); do
  [[ ! -S /tmp/.X11-unix/X99 ]] || break
  sleep 0.1
done
dbus-run-session -- python3 "$script_root/scripts/smoke-installed.py" "$expected"
case "$build_target" in
  ubuntu*|debian*) apt-get remove -y linux-app-manager ;;
  fedora*) dnf remove -y linux-app-manager ;;
  arch) pacman -R --noconfirm linux-app-manager ;;
esac
[[ ! -e /usr/bin/linux-app-manager && ! -e "$lam" ]]
printf 'Native installed package smoke passed for %s\n' "$build_target"
