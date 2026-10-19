#!/usr/bin/env bash
# Runtime-only validation of newly composed metadata, before public deployment.
set -euo pipefail
[[ $# == 2 && -f /.dockerenv && ${LAM_DISPOSABLE_BUILDER:-} == 1 ]] || exit 2
suite="$1"
repository=$(realpath "$2")
case "$suite" in ubuntu24.04|ubuntu26.04|debian13) ;; *) exit 2 ;; esac
printf 'deb [arch=amd64 signed-by=%s/vin-linuxmanager.gpg] file:%s %s main\n' \
  "$repository" "$repository" "$suite" > /etc/apt/sources.list.d/vin-linuxmanager.list
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y linux-app-manager
version=$(dpkg-query -W -f='${Version}' linux-app-manager)
[[ "$version" == *"$suite" ]]
export HOME=/tmp/lam-apt-install-home
mkdir -p "$HOME"
/usr/lib/linux-app-manager/lam list --all --json > /tmp/lam-apt-inventory.json
python3 - <<'PY'
import json
inventory = json.load(open('/tmp/lam-apt-inventory.json'))
assert any(p['source']=='apt' and p['healthy'] for p in inventory['providers'])
assert any(a.get('package_name')=='linux-app-manager' for a in inventory['apps'])
PY
apt-get remove -y linux-app-manager
[[ ! -e /usr/lib/linux-app-manager/lam ]]
printf 'Generated signed APT installation passed: %s %s\n' "$suite" "$version"
