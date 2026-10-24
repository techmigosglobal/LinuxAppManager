#!/usr/bin/env bash
# Destructive acceptance is confined to a newly provisioned QEMU guest.
set -euo pipefail
[[ $# == 1 && $EUID == 0 && ${LAM_DISPOSABLE_VM:-} == 1 && -f /run/lam-disposable-acceptance && ! -f /.dockerenv ]]
[[ $(systemd-detect-virt --vm) == qemu || $(systemd-detect-virt --vm) == kvm ]]
target=$1
cd /home/lamtest/acceptance
source /etc/os-release
case "$target:$ID:${VERSION_ID:-rolling}" in
  ubuntu24.04:ubuntu:24.04|ubuntu26.04:ubuntu:26.04|debian13:debian:13|fedora43:fedora:43|fedora44:fedora:44|arch:arch:*) ;;
  *) echo "wrong guest distribution: $target $ID ${VERSION_ID:-}" >&2; exit 1 ;;
esac
printf 'Guest identity: %s; kernel: %s; virtualization: %s\n' "$PRETTY_NAME" "$(uname -r)" "$(systemd-detect-virt)"
# Load before Arch's full update can replace modules for its booted kernel.
if [[ "$target" == arch ]]; then modprobe fuse; fi
# Only runtime desktop dependencies and a disposable leaf package enter the VM.
case "$target" in
  ubuntu*|debian*)
    provider=apt
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y dbus-x11 xvfb openbox hello python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 pkexec libfuse2t64
    package=$(find packages -maxdepth 1 -name "linux-app-manager_*${target}*_amd64.deb")
    apt-get install -y "$(realpath "$package")"
    ;;
  fedora*)
    provider=dnf
    dnf install -y dbus-daemon xorg-x11-server-Xvfb openbox hello python3-gobject polkit fuse-libs
    package=$(find packages -maxdepth 1 -name 'linux-app-manager-[0-9]*.x86_64.rpm')
    dnf install -y "$(realpath "$package")"
    ;;
  arch)
    provider=pacman
    pacman -Syu --noconfirm --needed dbus xorg-server-xvfb openbox hello python-gobject polkit fuse2
    package=$(find packages -maxdepth 1 -name 'linux-app-manager-[0-9]*-x86_64-arch.pkg.tar.zst')
    pacman -U --noconfirm "$package"
    ;;
esac
[[ -f "$package" ]]
systemctl start polkit
runuser -u lamtest -- python3 accept-polkit-cancel.py
export HOME=/root
export XDG_STATE_HOME=/root/.local/state
export XDG_RUNTIME_DIR=/run/lam-acceptance-runtime
install -d -m 700 "$XDG_RUNTIME_DIR"
Xvfb :99 -screen 0 1280x800x24 -nolisten tcp > /tmp/lam-xvfb.log 2>&1 &
display_pid=$!
trap 'kill "$display_pid" 2>/dev/null || true' EXIT
export DISPLAY=:99
for attempt in $(seq 1 100); do
  [[ ! -S /tmp/.X11-unix/X99 ]] || break
  sleep 0.1
done
dbus-run-session -- bash -c 'openbox >/tmp/lam-openbox.log 2>&1 & exec python3 accept-installed-gui.py "$1"' _ "$provider"
lam=/usr/lib/linux-app-manager/lam
"$lam" history --json > /tmp/history-before-upgrade.json
# All channels must preserve history through package replacement. For the new
# RPM/Arch channels there is no previous published package: report reinstall
# separately instead of inventing an upgrade from an unreleased version.
case "$target" in
  ubuntu*|debian*)
    if compgen -G 'previous/*.deb' > /dev/null; then
      apt-get install --allow-downgrades -y "$(realpath previous/*.deb)"
      dpkg-query -W -f='${Version}\n' linux-app-manager
      apt-get install -y "$(realpath "$package")"
      echo 'Previous public DEB to signed current DEB upgrade passed'
    else
      echo 'Missing previous signed DEB' >&2; exit 1
    fi
    ;;
  fedora*) dnf reinstall -y "$(realpath "$package")" ;;
  arch) pacman -U --noconfirm "$package" ;;
esac
"$lam" history --json > /tmp/history-after-upgrade.json
cmp /tmp/history-before-upgrade.json /tmp/history-after-upgrade.json
dbus-run-session -- python3 smoke-installed.py "$provider"
for sandbox in SNAP FLATPAK_ID; do
  if env "$sandbox=acceptance.test" "$lam" uninstall invalid --yes > /tmp/lam-sandbox-result 2>&1; then
    echo 'Sandbox host mutation guard failed' >&2; exit 1
  fi
  grep -q 'disabled in sandboxed builds' /tmp/lam-sandbox-result
done
if [[ -f packages/VIN-LinuxManager-0.1.1-x86_64.AppImage ]]; then
  image=$(realpath packages/VIN-LinuxManager-0.1.1-x86_64.AppImage)
  chmod +x "$image"
  modprobe fuse
  [[ -c /dev/fuse ]]
  dbus-run-session -- "$image" --appimage-smoke-test
  echo 'Normal FUSE AppImage GUI launch passed'
  mkdir /tmp/lam-appimage-extracted
  (cd /tmp/lam-appimage-extracted && "$image" --appimage-extract > /tmp/lam-appimage-extract.log)
  # Hide the device after the normal launch; extraction must work without FUSE.
  mv /dev/fuse /dev/fuse.acceptance-disabled
  dbus-run-session -- /tmp/lam-appimage-extracted/squashfs-root/AppRun --appimage-smoke-test
  [[ ! -e /dev/fuse ]]
  mv /dev/fuse.acceptance-disabled /dev/fuse
  echo 'Extracted AppImage GUI launch passed with the FUSE device unavailable'
fi
case "$target" in
  ubuntu*|debian*) apt-get remove -y linux-app-manager ;;
  fedora*) dnf remove -y linux-app-manager ;;
  arch) pacman -R --noconfirm linux-app-manager ;;
esac
[[ ! -e /usr/bin/linux-app-manager && ! -e "$lam" ]]
printf 'Desktop VM acceptance passed: %s\n' "$target"
