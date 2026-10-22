#!/usr/bin/env bash
# Run INSIDE the matching clean distribution builder; no host installation.
set -euo pipefail
if [[ $# != 3 ]]; then
  echo 'usage: build-native.sh TARGET SOURCE_ARCHIVE OUTPUT_DIR' >&2
  exit 2
fi
build_target="$1"
source_archive="$(realpath "$2")"
output_dir="$(realpath -m "$3")"
script_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
case "$build_target" in
  ubuntu24.04) expected_id=ubuntu; expected_version=24.04 ;;
  ubuntu26.04) expected_id=ubuntu; expected_version=26.04 ;;
  debian13) expected_id=debian; expected_version=13 ;;
  fedora43) expected_id=fedora; expected_version=43 ;;
  fedora44) expected_id=fedora; expected_version=44 ;;
  arch) expected_id=arch; expected_version='' ;;
  *) echo "unsupported native build target: $build_target" >&2; exit 2 ;;
esac
# shellcheck disable=SC1091
source /etc/os-release
[[ "$ID" == "$expected_id" && ( -z "$expected_version" || "${VERSION_ID:-}" == "$expected_version" ) ]] || {
  echo "target $build_target requires its matching clean builder; found $ID ${VERSION_ID:-rolling}" >&2; exit 1;
}
[[ "$(uname -m)" == x86_64 ]] || { echo 'native release currently supports x86_64 only' >&2; exit 1; }
for tool in python3 tar sha256sum cargo rustc desktop-file-validate appstreamcli; do
  command -v "$tool" >/dev/null || { echo "required build tool missing: $tool" >&2; exit 1; }
done
compiler_root="${LAM_RUST_TOOLCHAIN_ROOT:-$(rustc --print sysroot)}"
[[ "$("$compiler_root/bin/rustc" --version)" == 'rustc 1.90.0 '* ]] || { echo 'Set LAM_RUST_TOOLCHAIN_ROOT to the complete pinned Rust 1.90.0 toolchain' >&2; exit 1; }
export PATH="$compiler_root/bin:$PATH"
export CARGO_NET_OFFLINE=true
export RUSTUP_TOOLCHAIN=1.90.0
export CARGO_HOME="${LAM_CARGO_HOME:-$(mktemp -d "${TMPDIR:-/tmp}/lam-cargo.XXXXXX")}"
work="$(mktemp -d "${TMPDIR:-/tmp}/lam-native.XXXXXX")"
trap 'rm -rf "$work"' EXIT
mkdir -p "$output_dir"
# Validate archive paths before extraction, including links. Reject archives that
# could write outside the single versioned source directory.
source_root="$(python3 - "$source_archive" "$work" <<'PY'
import pathlib, re, sys, tarfile
archive, work = sys.argv[1:]
match = re.fullmatch(r'linux-app-manager-(\d+\.\d+\.\d+)\.tar\.gz', pathlib.Path(archive).name)
if not match:
    sys.exit('expected linux-app-manager-VERSION.tar.gz')
root = 'linux-app-manager-' + match[1]
with tarfile.open(archive) as tar:
    for member in tar.getmembers():
        p = pathlib.PurePosixPath(member.name)
        if not p.parts or p.parts[0] != root or p.is_absolute() or '..' in p.parts or member.isdev():
            sys.exit('unsafe source archive member: ' + member.name)
        if member.issym() or member.islnk():
            target = pathlib.PurePosixPath(member.linkname)
            if target.is_absolute() or '..' in target.parts:
                sys.exit('unsafe source archive link: ' + member.name)
    tar.extractall(work, filter='data')
print(str(pathlib.Path(work) / root))
PY
)"
cd "$source_root"
[[ -d vendor && -s .cargo/config.toml && -s Cargo.lock && -s THIRD_PARTY_LICENSES/inventory.json ]] || { echo 'offline source archive must include vendor/, .cargo/config.toml, Cargo.lock and collected THIRD_PARTY_LICENSES' >&2; exit 1; }
version="$(python3 -c 'import tomllib; print(tomllib.load(open("Cargo.toml", "rb"))["package"]["version"])')"
[[ "$(basename "$source_root")" == "linux-app-manager-$version" ]] || { echo 'archive directory/version mismatch' >&2; exit 1; }
if [[ -f source-origin.json ]]; then
  SOURCE_DATE_EPOCH="$(python3 -c 'import json; d=json.load(open("source-origin.json")); print(d.get("source_date_epoch",d.get("epoch",0)))')"
  export SOURCE_DATE_EPOCH
fi
desktop-file-validate packaging/io.github.techmigosglobal.LinuxAppManager.desktop
appstreamcli validate --no-net packaging/io.github.techmigosglobal.LinuxAppManager.metainfo.xml
case "$build_target" in
  ubuntu*|debian*)
    command -v dpkg-buildpackage >/dev/null
    command -v lintian >/dev/null
    # A real, private build-dependency package is necessary on old Ubuntu. It
    # includes the actual pinned toolchain and satisfies versioned Provides.
    if ! dpkg-checkbuilddeps 2>/dev/null; then
      "$script_root/scripts/package-rust-toolchain.sh" "$compiler_root" "$work/toolchain"
      dpkg -i "$work/toolchain/lam-rust-toolchain_1.90.0_amd64.deb"
    fi
    dpkg-checkbuilddeps
    python3 - "$build_target" <<'PY'
from pathlib import Path
import re, sys
path = Path('debian/changelog')
text = path.read_text()
text = re.sub(r'^(linux-app-manager \()[^)]*', lambda m: m[1] + re.search(r'^version = "([^"]+)"', Path('Cargo.toml').read_text(), re.M)[1] + '-1~' + sys.argv[1], text, count=1)
path.write_text(text)
PY
    dpkg-buildpackage -us -uc -b
    shopt -s nullglob
    packages=("$work"/linux-app-manager_*.deb)
    (( ${#packages[@]} > 0 )) || { echo 'no Debian packages produced' >&2; exit 1; }
    for package in "${packages[@]}"; do
      lintian --fail-on error "$package"
      dpkg-deb --info "$package" >/dev/null
      "$script_root/scripts/verify-clean-debian.sh" --artifact "$package"
      cp "$package" "$output_dir/"
    done
    for artifact in "$work"/*.buildinfo "$work"/*.changes; do
      [[ ! -f "$artifact" ]] || cp "$artifact" "$output_dir/"
    done
    ;;
  fedora*)
    command -v rpmbuild >/dev/null
    command -v rpmlint >/dev/null
    rpm_root="$work/rpmbuild"
    mkdir -p "$rpm_root"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
    cp "$source_archive" "$rpm_root/SOURCES/"
    cp rpm/linux-app-manager.spec "$rpm_root/SPECS/"
    rpmbuild --define "_topdir $rpm_root" --define "dist .fc${expected_version}" -ba "$rpm_root/SPECS/linux-app-manager.spec"
    mapfile -t packages < <(find "$rpm_root/RPMS" "$rpm_root/SRPMS" -type f -name '*.rpm')
    (( ${#packages[@]} > 0 )) || { echo 'no RPM packages produced' >&2; exit 1; }
    rpmlint "${packages[@]}"
    cp "${packages[@]}" "$output_dir/"
    ;;
  arch)
    command -v makepkg >/dev/null
    command -v namcap >/dev/null
    # Arch forbids every makepkg operation as root, including --printsrcinfo
    # inside the renderer. Establish one unprivileged context before rendering.
    if [[ "$(id -u)" == 0 ]]; then
      id lam-builder >/dev/null 2>&1 || useradd --create-home lam-builder
      chown -R lam-builder:lam-builder "$work" "$CARGO_HOME"
      chmod o+x "$work"
      run_arch_user() {
        runuser -u lam-builder -- env PATH="$PATH" CARGO_HOME="$CARGO_HOME" CARGO_NET_OFFLINE=true RUSTUP_TOOLCHAIN=1.90.0 "$@"
      }
    else
      run_arch_user() { "$@"; }
    fi
    run_arch_user python3 "$script_root/scripts/render-aur.py" "$source_archive" "$work/aur"
    missing="$(pacman -T python python-gobject gtk4 libadwaita polkit 'rust>=1.90' gcc pkgconf || true)"
    [[ -z "$missing" ]] || { echo "Arch dependencies missing: $missing" >&2; exit 1; }
    # Use the checksummed local archive so makepkg requires no source download.
    cp "$source_archive" "$work/aur/"
    run_arch_user bash -c 'cd "$1"; makepkg --cleanbuild --noconfirm --check' _ "$work/aur"
    mapfile -t packages < <(find "$work/aur" -maxdepth 1 -name '*.pkg.tar.zst')
    (( ${#packages[@]} > 0 )) || { echo 'no Arch packages produced' >&2; exit 1; }
    namcap "$work/aur/PKGBUILD" "${packages[@]}"
    for package in "${packages[@]}"; do
      cp "$package" "$output_dir/$(basename "$package" .pkg.tar.zst)-arch.pkg.tar.zst"
    done
    tar -C "$work/aur" -czf "$output_dir/linux-app-manager-$version-aur.tar.gz" PKGBUILD .SRCINFO
    ;;
esac
python3 - "$build_target" "$source_archive" "$output_dir" <<'PY'
import hashlib, json, pathlib, platform, subprocess, sys
build_target, source, output = sys.argv[1:]
def command(*args):
    return subprocess.check_output(args, text=True).strip()
report = {'target':build_target, 'architecture':platform.machine(), 'os_release':pathlib.Path('/etc/os-release').read_text(), 'rustc':command('rustc','--version','--verbose'), 'cargo':command('cargo','--version'), 'source_sha256':hashlib.sha256(pathlib.Path(source).read_bytes()).hexdigest(), 'offline_cargo':True, 'result':'build-and-package-checks-passed', 'limitations':['Desktop VM installation and functional acceptance are separate checks.']}
package_tool = ['dpkg-query','-W'] if build_target.startswith(('ubuntu','debian')) else ['rpm','-qa'] if build_target.startswith('fedora') else ['pacman','-Q']
report['builder_packages'] = command(*package_tool).splitlines()
pathlib.Path(output, f'builder-{build_target}.json').write_text(json.dumps(report, indent=2)+'\n')
PY
