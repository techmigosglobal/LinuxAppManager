#!/usr/bin/env bash
# Public installation acceptance, isolated from the publisher's workstation.
set -euo pipefail
[[ $# == 1 && -f /.dockerenv && ${LAM_DISPOSABLE_BUILDER:-} == 1 ]] || {
  echo 'public APT smoke requires an explicitly disposable Docker container' >&2; exit 2;
}
suite="$1"
case "$suite" in ubuntu24.04|ubuntu26.04|debian13) ;; *) exit 2 ;; esac
base_url=https://techmigosglobal.github.io/LinuxAppManager/apt
expected_fingerprint=DE6DC03A1F11C0176188BBAC6E75CBCE90CE3F16
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl gnupg dbus-x11 xvfb
install -d -m 0755 /etc/apt/keyrings
curl --retry 5 --retry-delay 5 --fail --location "$base_url/vin-linuxmanager.gpg" \
  -o /etc/apt/keyrings/vin-linuxmanager.gpg
fingerprint=$(gpg --show-keys --with-colons /etc/apt/keyrings/vin-linuxmanager.gpg | awk -F: '$1=="fpr" {print $10; exit}')
[[ "$fingerprint" == "$expected_fingerprint" ]]
# Construct the known source explicitly, rather than executing downloaded text.
printf 'Types: deb\nURIs: %s\nSuites: %s\nComponents: main\nArchitectures: amd64\nSigned-By: /etc/apt/keyrings/vin-linuxmanager.gpg\n' \
  "$base_url" "$suite" > /etc/apt/sources.list.d/vin-linuxmanager.sources
apt-get update
apt-get install -y linux-app-manager
installed_version=$(dpkg-query -W -f='${Version}' linux-app-manager)
[[ "$installed_version" == *"$suite" ]]
export HOME=/tmp/lam-public-install-home
mkdir -p "$HOME"
/usr/lib/linux-app-manager/lam list --all --json > /tmp/public-inventory.json
script_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
dbus-run-session -- xvfb-run -a python3 "$script_root/scripts/smoke-installed.py" apt
mapfile -t versions < <(apt-cache madison linux-app-manager | awk '{print $3}' | awk '!seen[$0]++')
if (( ${#versions[@]} > 1 )); then
  previous="${versions[1]}"
  [[ "$previous" == *"$suite" ]]
  apt-get install -y --allow-downgrades "linux-app-manager=$previous"
  [[ $(dpkg-query -W -f='${Version}' linux-app-manager) == "$previous" ]]
  apt-get install -y "linux-app-manager=$installed_version"
  [[ $(dpkg-query -W -f='${Version}' linux-app-manager) == "$installed_version" ]]
else
  printf 'First compatible release: no retained predecessor for %s\n' "$suite"
fi
apt-get remove -y linux-app-manager
[[ ! -e /usr/lib/linux-app-manager/lam ]]
printf 'Public signed APT installation passed: %s %s\n' "$suite" "$installed_version"
