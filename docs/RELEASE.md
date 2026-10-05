# Release and store submission

For the full artifact-by-artifact build, store, signing, CI, and rollback
procedure, see [DISTRIBUTION_GUIDE.md](DISTRIBUTION_GUIDE.md).

## Artifact policy

Native Debian, RPM, and Arch packages are the operational release artifacts.
They run against the host package databases and request authorization through
the desktop Polkit session. Snap and Flatpak artifacts must not expose an
unreviewed host mutation boundary. The GUI disables host package changes when
it detects Flatpak or Snap; the manifests remain inventory/history starting points
until a reviewed helper and store-specific permission model are completed.

## Clean-room release steps

1. Create an annotated version tag and record its immutable commit.
2. Run `scripts/release-audit.sh` and `scripts/verify-package-recipes.sh`.
3. Run `RUSTUP_TOOLCHAIN=1.90.0 cargo test --all-targets`, `cargo fmt --check`,
   and `cargo clippy --all-targets -- -D warnings`.
4. Run `scripts/verify-clean-debian.sh` in its pinned Ubuntu builder, then build
   the native package in clean RPM and Arch builders. Keep each builder's image
   digest and logs with the release evidence.
5. Run `scripts/write-release-manifest.sh DIST_OR_ARTIFACT_DIR` to generate
   checksums, a file manifest, and a Cargo dependency SBOM; inspect packages for `target/`,
   `.git/`, caches, credentials, signing keys, and user data.
6. Create or load the passphrase-protected GPG release key with
   `scripts/create-release-signing-key.sh`, then sign artifacts with
   `scripts/sign-release.sh`. Verify them with
   `scripts/verify-release-signatures.sh`.
7. Submit the native artifacts to the relevant repository/store and retain the
   previous version for rollback.

## Rollback

If a release reports incorrect inventory or a destructive-operation regression,
stop publication, remove the affected store version if permitted, and restore
the previous package. The SQLite state database is local user state and is not
part of any package artifact; newer binaries must tolerate older schemas.

## External prerequisites

Store publication still requires review metadata and store-specific
acceptance. The public repository identity, support domain, maintainer email,
license file, Debian copyright metadata, screenshots, and release-signing
workflow are now present. The private signing key and store account secrets
remain outside this repository.
