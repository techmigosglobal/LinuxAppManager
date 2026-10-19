#!/usr/bin/env bash
# Private binary-build prerequisite for distributions whose Rust is too old.
# This is a real package containing the compiler, not a dependency-check bypass.
set -euo pipefail
if [[ $# != 2 ]]; then
  echo 'usage: package-rust-toolchain.sh TOOLCHAIN_ROOT OUTPUT_DIR' >&2
  exit 2
fi
compiler_root="$(realpath "$1")"
output_dir="$(realpath -m "$2")"
[[ "$("$compiler_root/bin/rustc" --version)" == 'rustc 1.90.0 '* ]] || { echo 'Requires actual Rust 1.90.0 toolchain' >&2; exit 1; }
[[ -x "$compiler_root/bin/cargo" ]] || { echo 'Toolchain has no cargo binary' >&2; exit 1; }
mkdir -p "$output_dir"
stage="$(mktemp -d "${TMPDIR:-/tmp}/lam-toolchain.XXXXXX")"
trap 'rm -rf "$stage"' EXIT
mkdir -p "$stage/opt/lam-rust-toolchain" "$stage/DEBIAN"
# Omit documentation only; retain the compiler sysroot, linker/runtime libraries,
# rustdoc and cargo so Cargo build scripts and all tests work without rustup.
tar -C "$compiler_root" --exclude='./share/doc' --exclude='./lib/rustlib/src' -cf - . | tar -C "$stage/opt/lam-rust-toolchain" -xf -
cat > "$stage/DEBIAN/control" <<'EOF'
Package: lam-rust-toolchain
Version: 1.90.0
Architecture: amd64
Maintainer: VIN-LinuxManager maintainers <Vin-Linux-App-Manager@techmigos.com>
Section: devel
Priority: optional
Provides: rustc (= 1.90.0), cargo (= 1.90.0)
Description: Pinned Rust toolchain for private VIN-LinuxManager binary builders
 Contains the actual Rust 1.90.0 compiler, Cargo and standard library.
 Build-only prerequisite, not installed with VIN-LinuxManager.
EOF
dpkg-deb --root-owner-group --build "$stage" "$output_dir/lam-rust-toolchain_1.90.0_amd64.deb"
