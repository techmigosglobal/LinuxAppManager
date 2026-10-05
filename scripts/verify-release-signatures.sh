#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 PUBLIC_KEY RELEASE_DIRECTORY" >&2
  exit 2
fi

public_key="$1"
release_dir="$2"
if [[ ! -f "$public_key" || ! -d "$release_dir" ]]; then
  echo "public key or release directory is missing" >&2
  exit 1
fi

verify_home="$(mktemp -d)"
trap 'rm -rf "$verify_home"' EXIT
chmod 700 "$verify_home"
gpg --homedir "$verify_home" --batch --import "$public_key" >/dev/null

mapfile -t release_files < <(
  find "$release_dir" -maxdepth 1 -type f \
    ! -name '*.asc' \
    ! -name '*.sig' \
    -print | sort
)
if [[ ${#release_files[@]} -eq 0 ]]; then
  echo "no release files found in: $release_dir" >&2
  exit 1
fi

for artifact in "${release_files[@]}"; do
  signature="${artifact}.asc"
  if [[ ! -f "$signature" ]]; then
    echo "missing detached signature: $signature" >&2
    exit 1
  fi
  gpg --homedir "$verify_home" --batch --verify "$signature" "$artifact" >/dev/null
  echo "verified: $(basename "$artifact")"
done
