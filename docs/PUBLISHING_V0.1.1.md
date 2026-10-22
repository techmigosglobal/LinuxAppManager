# v0.1.1 publishing procedure

The release workflow has two modes. **Preflight** builds a source snapshot of
the exact workflow commit, runs validation and builds all six native targets;
it never creates a release. An official run requires immutable tag `v0.1.1`
matching every package version and creates a **signed draft**, preserving
`v0.1.0` and any existing release.

## Validate and build

```sh
cargo fmt --all -- --check
cargo test --locked --all-targets
cargo clippy --locked --all-targets -- -D warnings
python3 -m unittest discover -s tests -p 'test_*.py'
./scripts/test-integration.sh
./scripts/release-audit.sh
```

Local tooling tests require `apt-utils`, `appstream`, `python3-pil`, GnuPG,
`desktop-file-utils`, `rpm` and GTK4/libadwaita with Xvfb. Source archives vendor
the exact Cargo.lock. `scripts/build-source.sh --local /tmp/lam-source` is
explicitly development-only. Official source generation uses
`scripts/build-source.sh v0.1.1 OUTPUT` and reads the tag, not dirty files.

After pushing the implementation branch, dispatch `release.yml` on that branch
with `version=0.1.1`, `preflight=true`, `build_appimage=true`. Review all six
builder reports and installation logs. Build images are recorded by digest;
Rust 1.90.0 and portable runtime tools are pinned. See `debian/README.source`
for the real build-only compiler package used on distributions with older Rust.
Private binary builds do not constitute official Debian/Ubuntu archive acceptance.

## Installation acceptance and promotion

Native jobs install the actual package in a fresh runtime container, scan its
real package database, launch the installed GUI through Xvfb, check sandbox
refusal and confirmation requirements, and remove the installed application.
AppImage jobs verify extraction without FUSE and launch the bundled GUI. These
are automated checks, not interactive desktop VM proof.

Before public promotion, retain clean-desktop evidence for each supported
distribution: launch, provider inventory, authorization cancellation, reviewed
disposable-package removal, operation history, upgrade, application uninstall,
and AppImage on Ubuntu/Fedora/Arch. Preserve the previous signed release.

Once preflight and installation acceptance pass, merge the reviewed source,
create/push the immutable `v0.1.1` tag, and let its workflow produce the signed
draft, including AppImage for tag-triggered builds. An explicit tagged retry
uses `preflight=false,build_appimage=true`; do not race two builds of the same
tag. Never change a tag or append unverified artifacts to an existing release.

Download the draft artifacts, verify every signature and `sha256sum --check
SHA256SUMS` from the download directory, and complete the acceptance record.
Promote with `gh release edit v0.1.1 --draft=false --latest` only when those gates
pass. The dependency inventory is labeled as such, not claimed as an SPDX SBOM.

## Signed APT and Pages

Pages rebuilds after a successful release workflow or an explicit dispatch.
After draft promotion, dispatch `website.yml` (editing a release does not fire
`workflow_run`). It selects the newest two complete public native releases,
verifies checksums and detached package signatures against the **committed public
key**, then builds separate `ubuntu24.04`, `ubuntu26.04`, and `debian13` suites.

The same deployment contains the website and `/apt/`; website changes cannot
erase the repository. Missing packages, keys or signatures fail before deployment
and preserve the previous site. Signed metadata covers Packages, compressed
indexes, by-hash targets, DEP-11 catalogs and icon archives. The GPG secret is
used only in an isolated temporary keyring with cleanup on exit.

Manual composition uses:

```sh
python3 scripts/collect-apt-packages.py --output /tmp/lam-packages \
  --public-key packaging/vin-linuxmanager-release-public-key.asc
python3 scripts/build-apt-repository.py --packages /tmp/lam-packages \
  --output /tmp/lam-apt --key-id DE6DC03A1F11C0176188BBAC6E75CBCE90CE3F16
python3 scripts/prepare-pages.py --website website \
  --apt-repository /tmp/lam-apt --output /tmp/lam-pages
```

Use the existing protected signing setup; never copy plaintext signing material
into the checkout or publish test keys. Fresh-client installation from the public
URL is required before changing the channel status to published.

## Other channels and external review

Copr receives the Fedora SRPMs from a verified release; authenticated submission,
successful per-version builds and fresh-client repository installation are
required. AUR receives the concrete recipe and `.SRCINFO`, not binaries; submit
using the maintainer's account only after the source asset is public.

Snap's registered name is `vin-linux-app-manager`. Read publisher status before
another upload; do not repeatedly retry the unchanged classic build. A strict
inventory edition needs working host inventory with approved interfaces before
it is useful. Keep host mutations disabled; a host helper is outside this release.

Flathub eligibility is unresolved for this host system utility. Its current
[requirements](https://docs.flathub.org/docs/for-app-authors/requirements) exclude
host system utilities and host-dependent core functionality and restrict
AI-assisted manifests/submission interactions. A human maintainer must establish
eligibility, author the manifest and handle submission; existing generated
templates must not be presented as compliant. Fedora Flatpak inclusion is a
separate review, and none of these reviews is implied by a native package build.

## Rollback and status

Keep the current and previous native packages and signed release downloads.
Recompose Pages from the retained verified releases if repository deployment
fails. Stop promotion on failed package/runtime checks. Record source commit,
artifact hash, builder digest, job URL, public install result, review URL and
assigned store revision in `PUBLISHING_STATUS.md`. Distinguish recipe, built,
uploaded, reviewed and publicly installable states.
