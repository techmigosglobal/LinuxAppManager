#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SIGNING_NAME="${RELEASE_SIGNING_NAME:-VIN-LinuxManager release signing}"
SIGNING_EMAIL="${RELEASE_SIGNING_EMAIL:-Vin-Linux-App-Manager@techmigos.com}"
IDENTITY="${SIGNING_NAME} <${SIGNING_EMAIL}>"

if ! command -v gpg >/dev/null 2>&1; then
  echo "gpg is required to create the release key" >&2
  exit 1
fi

if [[ $# -gt 1 ]]; then
  echo "usage: $0 [identity]" >&2
  exit 2
fi

if [[ $# -eq 1 ]]; then
  IDENTITY="$1"
fi

if gpg --list-secret-keys --with-colons "$IDENTITY" | grep -q '^sec:'; then
  echo "a secret key already exists for: $IDENTITY" >&2
  exit 1
fi

echo "Creating a passphrase-protected RSA release-signing key for: $IDENTITY"
generate_options=()
if [[ -n "${RELEASE_KEY_PASSPHRASE_FILE:-}" ]]; then
  if [[ ! -f "$RELEASE_KEY_PASSPHRASE_FILE" ]]; then
    echo "RELEASE_KEY_PASSPHRASE_FILE does not exist: $RELEASE_KEY_PASSPHRASE_FILE" >&2
    exit 1
  fi
  generate_options=(--batch --pinentry-mode loopback --passphrase-file "$RELEASE_KEY_PASSPHRASE_FILE")
else
  echo "GPG will ask for the passphrase through the configured pinentry agent."
fi
gpg "${generate_options[@]}" --quick-generate-key "$IDENTITY" rsa4096 sign 3y

fingerprint="$(gpg --with-colons --list-secret-keys "$IDENTITY" \
  | awk -F: '$1 == "fpr" { print $10; exit }')"
if [[ -z "$fingerprint" ]]; then
  echo "could not determine the new key fingerprint" >&2
  exit 1
fi

public_dir="$ROOT/dist/signing"
mkdir -p "$public_dir"
gpg --armor --export "$fingerprint" > "$public_dir/vin-linuxmanager-release-public-key.asc"
printf '%s\n' "$fingerprint" > "$public_dir/vin-linuxmanager-release-key-fingerprint.txt"
chmod 0644 "$public_dir/vin-linuxmanager-release-public-key.asc" \
  "$public_dir/vin-linuxmanager-release-key-fingerprint.txt"

cat <<EOF
Release key created.
Fingerprint: $fingerprint
Public key:  $public_dir/vin-linuxmanager-release-public-key.asc
Fingerprint: $public_dir/vin-linuxmanager-release-key-fingerprint.txt

Keep the secret key in a protected offline backup. Never commit or upload the
secret key. Export it to a protected file only when configuring the CI secret:

  gpg --armor --export-secret-keys "$fingerprint" > /protected/path/release-private-key.asc
  chmod 600 /protected/path/release-private-key.asc
EOF
