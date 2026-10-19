#!/usr/bin/env bash
# Usage: build-source.sh TAG OUTPUT_DIRECTORY | build-source.sh --local OUTPUT_DIRECTORY
# Official archives always read the exact tag. --local explicitly permits working-tree edits.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
[[ $# -eq 2 ]] || { echo "usage: $0 TAG|--local OUTPUT_DIRECTORY" >&2; exit 2; }
source_ref="$1"
output_dir="$(realpath -m -- "$2")"
work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT
if [[ "$source_ref" == --local ]]; then
  commit="$(git -C "$ROOT" rev-parse HEAD)"
  epoch="$(git -C "$ROOT" show -s --format=%ct HEAD)"
  mkdir -p "$work_dir/source"
  # Explicit local mode includes changed and new, nonignored source files only.
  git -C "$ROOT" ls-files -z --cached --others --exclude-standard |
    python3 -c 'import os,sys; root=os.fsencode(sys.argv[1]); sys.stdout.buffer.write(b"\0".join(p for p in sys.stdin.buffer.read().split(b"\0") if p and os.path.lexists(os.path.join(root,p)))+b"\0")' "$ROOT" > "$work_dir/source-files"
  tar -C "$ROOT" --null -T "$work_dir/source-files" -cf - |
    tar -C "$work_dir/source" -xf -
else
  [[ "$source_ref" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "expected an immutable release tag vX.Y.Z" >&2; exit 2; }
  commit="$(git -C "$ROOT" rev-parse --verify "refs/tags/$source_ref^{commit}")"
  epoch="$(git -C "$ROOT" show -s --format=%ct "$commit")"
  mkdir -p "$work_dir/source"
  git -C "$ROOT" archive "$commit" | tar -C "$work_dir/source" -xf -
fi
version="$(python3 "$ROOT/scripts/check-release-version.py" --root "$work_dir/source")"
if [[ "$source_ref" != --local && "$source_ref" != "v$version" ]]; then
  echo "tag and source version differ" >&2; exit 1
fi
source_dir="$work_dir/linux-app-manager-$version"
mv "$work_dir/source" "$source_dir"
mkdir -p "$source_dir/.cargo"
(cd "$source_dir" && cargo vendor --locked --versioned-dirs vendor > .cargo/config.toml)
# Preserve dependency license and notice texts in every source/binary distribution.
python3 "$source_dir/scripts/collect-vendor-licenses.py" "$source_dir"
# Verify the resulting configuration really resolves the entire lockfile offline.
(cd "$source_dir" && cargo metadata --offline --locked --format-version 1 > /dev/null)
python3 - "$source_dir" "$version" "$commit" "$source_ref" "$epoch" <<'PY'
import json, pathlib, sys
root, version, commit, ref, epoch = sys.argv[1:]
(pathlib.Path(root) / "source-origin.json").write_text(json.dumps({
    "version": version, "commit": commit, "ref": ref,
    "source_date_epoch": int(epoch), "local_worktree": ref == "--local",
}, sort_keys=True, indent=2) + "\n")
PY
mkdir -p "$output_dir"
tar --sort=name --mtime="@$epoch" --owner=0 --group=0 --numeric-owner \
  -C "$work_dir" -cf - "linux-app-manager-$version" |
  gzip -n > "$output_dir/linux-app-manager-$version.tar.gz"
echo "$output_dir/linux-app-manager-$version.tar.gz"
