#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 KEY_ID RELEASE_DIRECTORY" >&2
  exit 2
fi

key_id="$1"
release_dir="$2"

if ! command -v gpg >/dev/null 2>&1; then
  echo "gpg is required to sign release artifacts" >&2
  exit 1
fi
if [[ ! -d "$release_dir" ]]; then
  echo "release directory does not exist: $release_dir" >&2
  exit 1
fi
if [[ -z "$key_id" ]]; then
  echo "a signing key ID or fingerprint is required" >&2
  exit 1
fi

sign_options=(--yes --local-user "$key_id" --armor --detach-sign)
if [[ -n "${GPG_PASSPHRASE_FILE:-}" ]]; then
  if [[ ! -f "$GPG_PASSPHRASE_FILE" ]]; then
    echo "GPG_PASSPHRASE_FILE does not exist: $GPG_PASSPHRASE_FILE" >&2
    exit 1
  fi
  sign_options+=(--batch --pinentry-mode loopback --passphrase-file "$GPG_PASSPHRASE_FILE")
fi

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
  gpg "${sign_options[@]}" --output "$signature" "$artifact"
  gpg --verify "$signature" "$artifact" >/dev/null
  echo "signed: $(basename "$artifact")"
done
