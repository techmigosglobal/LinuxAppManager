#!/usr/bin/env bash
set -euo pipefail
[[ $# -eq 2 ]] || { echo "usage: $0 KEY_ID RELEASE_DIRECTORY" >&2; exit 2; }
key_id="$1"
release_dir="$2"
command -v gpg >/dev/null || { echo "gpg is required" >&2; exit 1; }
[[ -d "$release_dir" && -n "$key_id" ]] || { echo "release directory and signing key are required" >&2; exit 1; }
[[ -f "$release_dir/SHA256SUMS" && -f "$release_dir/MANIFEST.json" ]] || { echo "generate the manifest before signing" >&2; exit 1; }
(cd "$release_dir" && sha256sum --check --strict SHA256SUMS)
sign_options=(--batch --yes --local-user "$key_id" --armor --detach-sign)
if [[ -n "${GPG_PASSPHRASE_FILE:-}" ]]; then
  [[ -f "$GPG_PASSPHRASE_FILE" ]] || { echo "passphrase file is missing" >&2; exit 1; }
  sign_options+=(--pinentry-mode loopback --passphrase-file "$GPG_PASSPHRASE_FILE")
fi
while IFS= read -r -d '' artifact; do
  signature="${artifact}.asc"
  gpg "${sign_options[@]}" --output "$signature" "$artifact"
  gpg --batch --verify "$signature" "$artifact" >/dev/null
  echo "signed: $(basename "$artifact")"
done < <(find "$release_dir" -type f \( ! -name '*.asc' -a ! -name '*.sig' -o -name 'vin-linuxmanager-release-public-key.asc' \) -print0 | sort -z)
