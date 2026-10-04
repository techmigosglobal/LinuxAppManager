#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "clean Debian verification requires Docker" >&2
  exit 1
fi

# Pin the builder image so a release check does not silently change when the
# mutable Ubuntu tag moves. Override this only when deliberately refreshing the
# builder and record the resulting digest in the release evidence.
BUILDER_IMAGE="${LAM_DEBIAN_BUILDER_IMAGE:-ubuntu@sha256:da6fc2be547864451aa253836dd926da33623312df4a9a243e35dc877c378a78}"
if [[ -n "${LAM_DEBIAN_ARTIFACT_DIR:-}" ]]; then
  ARTIFACT_DIR="$LAM_DEBIAN_ARTIFACT_DIR"
else
  ARTIFACT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/linux-app-manager-deb.XXXXXX")"
fi
mkdir -p "$ARTIFACT_DIR"

echo "building Debian artifact in ${BUILDER_IMAGE}"
docker run --rm \
  --mount "type=bind,src=${ROOT},dst=/src,readonly" \
  --mount "type=bind,src=${ARTIFACT_DIR},dst=/out" \
  "$BUILDER_IMAGE" bash -euo pipefail -c '
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y --no-install-recommends \
      build-essential \
      ca-certificates \
      cargo \
      debhelper-compat \
      dpkg-dev \
      gir1.2-adw-1 \
      gir1.2-gtk-4.0 \
      python3 \
      python3-gi \
      rustc

    printf "builder: "
    rustc --version
    printf "builder: "
    cargo --version

    rm -rf /tmp/linux-app-manager
    mkdir -p /tmp/linux-app-manager
    tar -C /src \
      --exclude=target \
      --exclude=dist \
      --exclude=.git \
      --exclude=__pycache__ \
      -cf - . | tar -C /tmp/linux-app-manager -xf -

    cd /tmp/linux-app-manager
    dpkg-buildpackage -us -uc -b

    shopt -s nullglob
    packages=(/tmp/linux-app-manager_*.deb)
    if (( ${#packages[@]} == 0 )); then
      echo "dpkg-buildpackage produced no Debian package" >&2
      exit 1
    fi
    cp "${packages[@]}" /out/
  '

shopt -s nullglob
packages=("$ARTIFACT_DIR"/linux-app-manager_*.deb)
if (( ${#packages[@]} == 0 )); then
  echo "no Debian package was written to ${ARTIFACT_DIR}" >&2
  exit 1
fi

for package in "${packages[@]}"; do
  echo "checking $(basename "$package")"
  dpkg-deb --info "$package" >/dev/null
  contents="$(dpkg-deb --contents "$package")"
  for required in \
    './usr/bin/linux-app-manager' \
    './usr/lib/linux-app-manager/lam' \
    './usr/lib/linux-app-manager/app.py' \
    './usr/share/applications/io.github.linuxappmanager.Lam.desktop' \
    './usr/share/metainfo/io.github.linuxappmanager.Lam.metainfo.xml' \
    './usr/share/icons/hicolor/scalable/apps/io.github.linuxappmanager.Lam.svg'; do
    if ! grep -Fq "$required" <<<"$contents"; then
      echo "package is missing ${required}: ${package}" >&2
      exit 1
    fi
  done
  if grep -Eq '(^|/)(target|\.git|__pycache__)(/|$)|(^|/)(\.env|.*\.pem|.*\.key)$' <<<"$contents"; then
    echo "package contains a build/cache/secret path: ${package}" >&2
    exit 1
  fi
  dpkg-deb --field "$package" Package Version Architecture
done

echo "clean Debian package verification: valid"
echo "artifacts: ${ARTIFACT_DIR}"
