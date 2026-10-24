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
DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl gnupg python3 dbus-x11 xvfb
install -d -m 0755 /etc/apt/keyrings
curl --retry 5 --retry-delay 5 --fail --location "$base_url/vin-linuxmanager.gpg" \
  -o /etc/apt/keyrings/vin-linuxmanager.gpg
fingerprint=$(gpg --show-keys --with-colons /etc/apt/keyrings/vin-linuxmanager.gpg | awk -F: '$1=="fpr" {print $10; exit}')
[[ "$fingerprint" == "$expected_fingerprint" ]]
# Verify APT itself rejects tampering with the actual published signed index.
# Keep this client's state and source separate from the normal installation.
rejection_root=$(mktemp -d /tmp/lam-public-apt-rejection.XXXXXX)
chmod 755 "$rejection_root"
mkdir -p "$rejection_root/repository/dists/$suite" "$rejection_root/client/state/lists/partial" \
  "$rejection_root/client/cache/archives/partial" "$rejection_root/client/etc/preferences.d" "$rejection_root/client/log"
curl --retry 5 --retry-delay 5 --fail --location "$base_url/dists/$suite/InRelease" \
  -o "$rejection_root/repository/dists/$suite/InRelease"
python3 - "$rejection_root" "$suite" <<'PY'
from pathlib import Path
import sys
root, suite = Path(sys.argv[1]), sys.argv[2]
index = root / 'repository/dists' / suite / 'InRelease'
original = index.read_bytes()
altered = original.replace(b'Origin: VIN-LinuxManager', b'Origin: altered')
assert original != altered, 'expected signed Origin field is missing'
index.write_bytes(altered)
client = root / 'client'
(client / 'state/status').touch()
(client / 'etc/sources.list').write_text(
    f'deb [arch=amd64 signed-by=/etc/apt/keyrings/vin-linuxmanager.gpg] '
    f'file:{root}/repository {suite} main\n')
(client / 'apt.conf').write_text(
    f'Dir "{client}";\nDir::State "state";\nDir::State::status "status";\n'
    'Dir::Cache "cache";\nDir::Etc "etc";\nDir::Etc::sourceparts "-";\n'
    'Dir::Etc::trusted "-";\nDir::Etc::trustedparts "-";\nDir::Log "log";\n'
    'APT::Sandbox::User "root";\nAcquire::Languages "none";\n'
    '#clear APT::Update::Post-Invoke;\n#clear APT::Update::Post-Invoke-Success;\n'
    '#clear DPkg::Post-Invoke;\n#clear DPkg::Pre-Invoke;\n#clear DPkg::Pre-Install-Pkgs;\n')
PY
if LC_ALL=C apt-get -c "$rejection_root/client/apt.conf" -o APT::Update::Error-Mode=any update \
  > "$rejection_root/result.txt" 2>&1; then
  echo 'APT accepted a modified public repository signature' >&2; exit 1
fi
grep -qi signature "$rejection_root/result.txt"
echo 'APT rejected tampering with the published repository signature'
# Construct the known source explicitly, rather than executing downloaded text.
printf 'Types: deb\nURIs: %s\nSuites: %s\nComponents: main\nArchitectures: amd64\nSigned-By: /etc/apt/keyrings/vin-linuxmanager.gpg\n' \
  "$base_url" "$suite" > /etc/apt/sources.list.d/vin-linuxmanager.sources
apt-get update
apt-get install -y linux-app-manager
# A second update must preserve the same authenticated candidate.
apt-get update
installed_version=$(dpkg-query -W -f='${Version}' linux-app-manager)
[[ "$installed_version" == *"$suite" ]]
candidate=$(LC_ALL=C apt-cache policy linux-app-manager | awk '/Candidate:/ {print $2; exit}')
[[ "$candidate" == "$installed_version" ]]
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
