#!/usr/bin/env bash
set -euo pipefail
[[ $# -eq 2 ]] || { echo "usage: $0 PUBLIC_KEY RELEASE_DIRECTORY" >&2; exit 2; }
public_key="$(realpath -- "$1")"
release_dir="$(realpath -- "$2")"
[[ -f "$public_key" && -d "$release_dir" && -f "$release_dir/SHA256SUMS" ]] || { echo "public key, release directory, or checksums are missing" >&2; exit 1; }
verify_home="$(mktemp -d)"
cleanup() {
  gpgconf --homedir "$verify_home" --kill all >/dev/null 2>&1 || true
  rm -rf "$verify_home"
}
trap cleanup EXIT
chmod 700 "$verify_home"
gpg --homedir "$verify_home" --batch --import "$public_key" >/dev/null
# Verify the signed checksum list before processing its untrusted paths.
gpg --homedir "$verify_home" --batch --verify "$release_dir/SHA256SUMS.asc" "$release_dir/SHA256SUMS" >/dev/null
python3 - "$release_dir" <<'PY'
import pathlib, re, sys
root = pathlib.Path(sys.argv[1])
lines = (root / 'SHA256SUMS').read_text().splitlines()
if not lines:
    raise SystemExit('empty checksum file')
for line in lines:
    if not re.fullmatch(r'[0-9a-f]{64}  .+', line):
        raise SystemExit('invalid checksum line')
    relative = pathlib.PurePosixPath(line[66:])
    if relative.is_absolute() or '..' in relative.parts or '\\' in str(relative):
        raise SystemExit('unsafe checksum path')
    path = root / relative
    if path.is_symlink() or not path.is_file() or root not in path.resolve().parents:
        raise SystemExit('checksum path is missing or outside the release')
PY
(cd "$release_dir" && sha256sum --check --strict SHA256SUMS)
while IFS= read -r -d '' artifact; do
  [[ -f "$artifact.asc" ]] || { echo "missing detached signature: $artifact.asc" >&2; exit 1; }
  gpg --homedir "$verify_home" --batch --verify "$artifact.asc" "$artifact" >/dev/null
  echo "verified: $(basename "$artifact")"
done < <(find "$release_dir" -type f \( ! -name '*.asc' -a ! -name '*.sig' -o -name 'vin-linuxmanager-release-public-key.asc' \) -print0 | sort -z)
