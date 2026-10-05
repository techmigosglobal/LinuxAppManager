# VIN-LinuxManager distribution and store guide

This guide explains how to turn a tagged VIN-LinuxManager release into native
packages, Flatpak/Snap artifacts, repository metadata, and a staged public
release.

The commands assume a real Git checkout with a public remote. The public
repository identity and first-release Flatpak ID are finalized, and v0.1.0 is
available as a GitHub release. Maintainer identity, legal license confirmation,
signing keys, store credentials, and some store-specific builder evidence are
still publisher-owned inputs. Do not replace those values with invented ones.

## 1. Choose the distribution model

There is no single package file that is correct for every Linux distribution.
Use one of these release tracks:

| Track | Artifact | Best audience | Publication route |
| --- | --- | --- | --- |
| Debian family | `.deb` plus a signed APT repository | Debian, Ubuntu, Mint, Pop!_OS and derivatives | PPA, Debian/Ubuntu archive, or your own APT repository |
| RPM family | `.rpm` plus signed repository metadata | Fedora, RHEL-compatible systems, openSUSE and derivatives | Fedora/Copr, OBS, vendor repository, or your own Yum/DNF repository |
| Arch family | `.pkg.tar.zst` | Arch Linux users | AUR for community packaging, or official Arch repositories through the maintainer process |
| Flatpak | OSTree repository/ref and optional `.flatpak` bundle | Most desktop distributions | Flathub submission or a signed private Flatpak repository |
| Snap | `.snap` revisions | Systems with snapd | Snap Store channels or a private store |
| Portable | AppImage | Users who do not want a package manager | AppImage download/signature distribution |

Native packages are the correct place for this application’s host package
manager operations. The current Flatpak and Snap code deliberately disables
host mutations when it detects `FLATPAK_ID` or `SNAP`; do not advertise
uninstall support from those sandboxed builds until a reviewed helper and
permission model exists.

Flatpak is not a binary-upload store. Flathub builds the application from a
manifest and its source references. Snap Store receives a built snap and
assigns a signed store revision. AUR stores packaging recipes, not built Arch
binary packages.

## 2. Release inputs that must be finalized first

Before creating a public tag, replace every intentional placeholder in the
repository:

1. Canonical public Git repository URL and the exact project owner.
2. Maintainer name and release email.
3. Final legal project license and a matching `LICENSE`/copyright file.
4. Final Flatpak application ID. For an `io.github.*` ID, the owner and
   repository components must map to the real GitHub project.
5. Store name, description, icon, screenshots, support URL, issue URL, and
   privacy/security contact if required by the store.
6. Target architectures: at least `x86_64`; add `aarch64` only after building
   and testing it.
7. Signing keys held outside the source tree and a protected CI environment.

The public source repository is `https://github.com/techmigosglobal/LinuxAppManager`
and the first-release Flatpak identity is `io.github.techmigosglobal.LinuxAppManager`.
The project website is `https://techmigosglobal.github.io/LinuxAppManager/`.
Maintainer contact, legal license confirmation, signing keys, and store
accounts still need to be supplied by the publisher.

## 3. Common release procedure

Run this process from a clean checkout after the final values are committed.

```bash
git status --short
git fetch --tags --prune

# Choose a release version only after deciding the versioning policy.
export VERSION=0.1.0
export TAG="v${VERSION}"
export RELEASE_DIR="$PWD/dist/$VERSION"
mkdir -p "$RELEASE_DIR"

git show --stat "$TAG"
git rev-parse "$TAG"
RUSTUP_TOOLCHAIN=1.90.0 cargo fmt --all -- --check
RUSTUP_TOOLCHAIN=1.90.0 cargo test --all-targets
RUSTUP_TOOLCHAIN=1.90.0 cargo clippy --all-targets -- -D warnings
./scripts/test-integration.sh
./scripts/release-audit.sh
./scripts/verify-package-recipes.sh
```

The tag must be immutable for the release record. After all artifacts are
built, run the release manifest generator for each artifact directory:

```bash
./scripts/write-release-manifest.sh "$RELEASE_DIR/deb"
./scripts/write-release-manifest.sh "$RELEASE_DIR/rpm"
./scripts/write-release-manifest.sh "$RELEASE_DIR/arch"
./scripts/write-release-manifest.sh "$RELEASE_DIR/flatpak"
./scripts/write-release-manifest.sh "$RELEASE_DIR/snap"
```

Inspect `SHA256SUMS`, `MANIFEST.json`, and `SBOM.cargo.json`. No artifact may
contain `.git`, `target`, Python caches, credentials, private keys, user data,
or a build directory.

Keep the previous release available until the new release has passed install,
upgrade, launch, scan, history, and removal-preview tests on every supported
platform. Do not test a real uninstall on a personal workstation; use a
disposable VM or a disposable package database.

## 4. Build the Debian/Ubuntu package

### 4.1 Install the native build tools

On Debian or Ubuntu, install the tools and runtime dependencies required by the
current recipe:

```bash
sudo apt-get update
sudo apt-get install --yes \
  build-essential cargo rustc debhelper-compat dpkg-dev \
  python3 python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 \
  policykit-1 lintian
```

The repository pins Rust 1.90 for development. The Debian package build must
use a system toolchain new enough for the `Build-Depends` declaration or an
approved packaging-toolchain policy.

### 4.2 Build and inspect the `.deb`

The recommended clean build uses Docker and a digest-pinned Ubuntu image:

```bash
LAM_DEBIAN_ARTIFACT_DIR="$RELEASE_DIR/deb" \
  ./scripts/verify-clean-debian.sh
```

The script builds with `dpkg-buildpackage`, checks the expected installed
paths, and rejects cache, source-control, or secret paths. To build directly
from the checkout for development:

```bash
dpkg-buildpackage -us -uc -b
```

Inspect before installing:

```bash
dpkg-deb --info "$RELEASE_DIR/deb/linux-app-manager_0.1.0_amd64.deb"
dpkg-deb --contents "$RELEASE_DIR/deb/linux-app-manager_0.1.0_amd64.deb"
lintian "$RELEASE_DIR/deb/linux-app-manager_0.1.0_amd64.deb"
```

Install and smoke-test on a disposable Debian-family VM:

```bash
sudo apt install "$RELEASE_DIR/deb/linux-app-manager_0.1.0_amd64.deb"
linux-app-manager
lam providers --json
lam list --json
lam history --json
```

Test an upgrade from the previous package and then a removal of the package
itself. Do not confuse removing the application package with testing the
application’s package-manager uninstall feature.

### 4.3 Publish to a Debian-family store

A `.deb` placed on a web page is not an APT repository. Software centers need
repository metadata and a signed repository index.

For Ubuntu users, the practical first route is a Launchpad PPA:

1. Convert the packaging to a proper non-native source package if submitting
   to an archive/PPA. The current local recipe uses `3.0 (native)` and does
   not yet include the final `debian/copyright`; fix this before archive
   submission.
2. Update `debian/changelog` with the final version, Debian revision, and
   maintainer identity.
3. Build a signed source upload, normally with `debuild -S -sa` or the
   project’s approved source-build tooling.
4. Upload the signed `.changes` file to the PPA with `dput`.
5. Wait for Launchpad’s build results for every selected Ubuntu series and
   architecture.
6. Test using the PPA’s generated repository instructions on a clean VM.

For a private/public APT repository that you operate yourself:

1. Build one package per supported Debian/Ubuntu architecture and series.
2. Create `Packages`, compressed package indexes, and a `Release` file with
   `apt-ftparchive`, `reprepro`, or an equivalent repository tool.
3. Sign the repository metadata with an offline or protected GPG key.
4. Publish the repository over HTTPS and provide the public key through a
   documented, fingerprint-verified channel.
5. Test `apt update`, install, upgrade, rollback, and uninstall on a clean VM.

For the official Debian or Ubuntu archives, expect source-package review,
policy checks, maintainer/sponsor requirements, and build-service compilation.
Uploading a binary `.deb` to a personal server does not enter those archives.

## 5. Build and publish the RPM package

### 5.1 Build an RPM locally

Build on Fedora for Fedora-compatible output. Use a clean Fedora/RHEL builder
for the exact target distribution rather than treating one RPM as universal.

```bash
sudo dnf install --yes \
  rpm-build rpmdevtools rust cargo gcc elfutils \
  python3-gobject gtk4 libadwaita polkit rpm-build

rpmdev-setuptree
mkdir -p "$RELEASE_DIR/rpm-source"
git archive --format=tar.gz \
  --prefix="linux-app-manager-${VERSION}/" \
  --output="$RELEASE_DIR/rpm-source/linux-app-manager-${VERSION}.tar.gz" \
  "$TAG"

export RPM_BUILD_ROOT="$(rpm --eval '%{_topdir}')"
cp "$RELEASE_DIR/rpm-source/linux-app-manager-${VERSION}.tar.gz" \
  "$RPM_BUILD_ROOT/SOURCES/"
cp rpm/linux-app-manager.spec "$RPM_BUILD_ROOT/SPECS/"
rpmbuild -ba "$RPM_BUILD_ROOT/SPECS/linux-app-manager.spec"
```

Inspect the result:

```bash
find "$RPM_BUILD_ROOT/RPMS" "$RPM_BUILD_ROOT/SRPMS" -type f -print
rpmlint "$RPM_BUILD_ROOT/RPMS"/*/linux-app-manager-*.rpm
rpm -qpl "$RPM_BUILD_ROOT/RPMS"/*/linux-app-manager-*.rpm
rpm -qpR "$RPM_BUILD_ROOT/RPMS"/*/linux-app-manager-*.rpm
```

Install the exact RPM on a disposable Fedora VM and test launch, scan, cache,
history, upgrade, and removal. Use `dnf install ./package.rpm`, not a copied
binary, so dependency resolution and ownership are exercised.

### 5.2 Build for several RPM targets

`rpmbuild` normally targets the builder’s own distribution and architecture.
For Fedora/RHEL variants and other architectures, create an SRPM and build it
with Mock or a service such as Copr:

```bash
rpmbuild -bs "$RPM_BUILD_ROOT/SPECS/linux-app-manager.spec"

sudo dnf install --yes mock mock-scm
mock -r <target-config> \
  "$RPM_BUILD_ROOT/SRPMS/linux-app-manager-${VERSION}-*.src.rpm"
```

Select a separate target for each supported Fedora/EPEL/RHEL release. Record
the builder image/configuration and dependency versions with the release.

### 5.3 Publish RPMs

For a project-owned RPM repository, publish one repository per supported
distribution/architecture where dependencies differ:

```bash
createrepo_c "$RELEASE_DIR/rpm-repository"
```

Sign each RPM and the repository metadata, serve it over HTTPS, and provide a
small `.repo` file containing the repository key and base URL. Test clean
installation and updates with DNF before announcing it.

For Fedora-oriented third-party distribution, Copr is usually simpler:

```bash
sudo dnf install --yes copr-cli
copr-cli create linux-app-manager --chroot fedora-rawhide-x86_64
copr-cli build linux-app-manager \
  "$RPM_BUILD_ROOT/SRPMS/linux-app-manager-${VERSION}-*.src.rpm"
```

Select the actual Fedora/EPEL chroots in the Copr project, wait for every
build to pass, then test the generated repository instructions. Do not claim
Fedora official-repository status merely because a Copr build succeeded;
official Fedora packages require the Fedora maintainer/review/build pipeline.
openSUSE users should be served through an OBS project or a repository built
for the exact openSUSE target.

## 6. Build and publish the Arch package

### 6.1 Prepare a real `PKGBUILD`

The current `arch/PKGBUILD` is a starting recipe. Before publishing it:

- replace the repository URL and commit placeholder;
- use the release tarball or an immutable Git tag/commit;
- replace `sha256sums=('SKIP')` with an actual checksum when using an archive;
- confirm dependencies and the final license;
- generate `.SRCINFO` from the final `PKGBUILD`;
- build in a clean Arch environment.

Build and validate locally:

```bash
sudo pacman -S --needed base-devel rust cargo python-gobject gtk4 libadwaita polkit
cd arch
makepkg --cleanbuild --syncdeps --rmdeps --check
namcap PKGBUILD
namcap linux-app-manager-*.pkg.tar.zst
sudo pacman -U linux-app-manager-*.pkg.tar.zst
```

`makepkg` produces a `.pkg.tar.zst`; `pacman -U` installs a local package.
Test upgrade and removal on an Arch VM. The package must not rely on files
that were present only on the build host.

### 6.2 Publish to AUR or official Arch repositories

AUR publication uploads the packaging recipe, not a prebuilt binary:

```bash
git clone https://aur.archlinux.org/linux-app-manager.git aur-linux-app-manager
cp arch/PKGBUILD aur-linux-app-manager/PKGBUILD
cd aur-linux-app-manager
makepkg --printsrcinfo > .SRCINFO
git add PKGBUILD .SRCINFO
git commit -m "linux-app-manager ${VERSION}"
git push
```

Use the real AUR package repository name after registering it. Users then
build the recipe locally with `makepkg`; AUR helpers are not a substitute for
reviewing the `PKGBUILD` and sources.

The official Arch repositories are a separate maintainer process. A package
being available in AUR does not mean it is in `extra` or endorsed by Arch.

## 7. Build and submit the Flatpak

### 7.1 Understand the current sandbox boundary

The current manifest uses the GNOME runtime and a source Git commit, and it
installs the Rust dependency manifest generated from `Cargo.lock`. It is
intended to be inventory/history-only until a reviewed host helper exists.
The current `--filesystem=host:ro` permission is not permission to mutate
host package databases and must not be presented as such.

Check the currently supported runtime branch before every release. Runtime
branches are maintained for a limited period; do not assume that GNOME 48
will remain acceptable just because it is in the current file.

### 7.2 Render and build locally

Install Flatpak, the GNOME SDK/Platform branch selected for the release, and
the Flatpak Builder tooling. The exact runtime branch must match the manifest.

```bash
flatpak remote-add --if-not-exists --user flathub \
  https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install -y flathub org.flatpak.Builder

export LAM_SOURCE_URL="https://PUBLIC-REPOSITORY.example/linux-app-manager"
export LAM_SOURCE_COMMIT="$(git rev-parse "$TAG")"
mkdir -p "$RELEASE_DIR/flatpak"
./scripts/render-flatpak.sh "$RELEASE_DIR/flatpak"
```

`render-flatpak.sh` must be able to run
`flatpak-cargo-generator.py`. It generates `cargo-sources.json` and a rendered
manifest with immutable source information. Review both before building.

Build, install, lint, and run:

```bash
flatpak-builder --force-clean \
  --user \
  --install-deps-from=flathub \
  --repo="$RELEASE_DIR/flatpak/repo" \
  --install \
  "$RELEASE_DIR/flatpak/builddir" \
  "$RELEASE_DIR/flatpak/io.github.techmigosglobal.LinuxAppManager.yml"

flatpak run io.github.techmigosglobal.LinuxAppManager
flatpak run --command=flatpak-builder-lint org.flatpak.Builder \
  manifest "$RELEASE_DIR/flatpak/io.github.techmigosglobal.LinuxAppManager.yml"
flatpak run --command=flatpak-builder-lint org.flatpak.Builder \
  repo "$RELEASE_DIR/flatpak/repo"
```

Test that the GUI starts, inventory is visible, history/cache work, and plan
or uninstall controls are disabled in the sandbox. A local single-file bundle
is useful for private testing, but it is not the Flathub submission:

```bash
flatpak build-bundle \
  "$RELEASE_DIR/flatpak/repo" \
  "$RELEASE_DIR/flatpak/linux-app-manager.flatpak" \
  io.github.techmigosglobal.LinuxAppManager \
  --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo
```

### 7.3 Prepare the Flathub submission

Flathub builds from a manifest in a GitHub repository. Do not commit the
`builddir`, `repo`, `.flatpak`, or application binaries to the submission
repository. Prepare these inputs instead:

- the final manifest;
- `cargo-sources.json` generated from the locked dependency file;
- `x-checker-data` so dependency/source updates can be checked;
- `only-arches` or `skip-arches` if the default `x86_64` and `aarch64` set is
  not correct;
- the upstream AppStream MetaInfo file, desktop file, icon, release entry,
  screenshots, and final license information.

The current MetaInfo file still needs the final URL/ID and screenshots. Every
module’s license files must be installed under
`$FLATPAK_DEST/share/licenses/$FLATPAK_ID` where required by the Flathub
policy.

Submission sequence:

1. Verify the public repository is reachable and the Flatpak ID maps to it.
2. Verify the domain/repository ownership required for Flathub verification.
3. Build and run locally with `org.flatpak.Builder`.
4. Run both manifest and repository lints and fix warnings/errors.
5. Fork `flathub/flathub` with its `new-pr` base available.
6. Add the manifest/dependency metadata on a branch based on `new-pr`.
7. Open a pull request against `new-pr`, not `master`.
8. Respond to reviewer comments and start the test build as instructed.
9. After merge and the official build, accept repository access and enable
   two-factor authentication.
10. Maintain the generated Flathub app repository for later updates; updates
    do not repeat the initial submission process.

The project owner must perform this submission and must review/disclose any
AI-generated application or packaging content according to Flathub’s current
policy. Do not automate a Flathub submission PR with an AI agent.

## 8. Build and publish the Snap

### 8.1 Resolve confinement before production

The current `snap/snapcraft.yaml` has `grade: devel` and `confinement: classic`.
`devel` is appropriate only for development and cannot be treated as a stable
production release. Classic confinement grants broad host access and needs
Snap Store approval before publication.

First prove whether inventory can work under strict confinement with the
smallest required interfaces. If the application truly requires classic
confinement, document why, remove unnecessary host access, retain the explicit
runtime mutation block, and request classic review from the store. Change to
`grade: stable` only after the artifact and confinement have passed testing.

### 8.2 Build and test locally

```bash
sudo snap install snapcraft --classic
snapcraft --version
snapcraft clean
snapcraft pack
```

For a locally built, unsigned development snap, install only on a disposable
test host:

```bash
sudo snap install ./linux-app-manager_0.1.0_amd64.snap \
  --dangerous --classic
snap run linux-app-manager
```

Use `--dangerous` only for local unsigned testing. It bypasses the normal
store assertion/signature path and is not a publication mechanism.

Build separately on each target architecture or use a trusted Snapcraft
remote-build service. Verify each resulting snap, not only the amd64 file.

### 8.3 Register and publish in stages

```bash
snapcraft login
snapcraft whoami
snapcraft register linux-app-manager

# Upload to a non-stable channel first.
snapcraft upload --release=edge ./linux-app-manager_0.1.0_amd64.snap
```

Install from the store on a different clean host and test it:

```bash
sudo snap install linux-app-manager --edge
snap run linux-app-manager
snap info linux-app-manager
```

After all supported architectures and clean-host tests pass, promote through
candidate and stable according to the store’s current command/UI. Keep the
revision number recorded in the release manifest. Store metadata, screenshots,
description, categories, support information, and classic-confinement review
must also be complete.

Snaps use channels such as `latest/edge`, `latest/beta`,
`latest/candidate`, and `latest/stable`. The store assigns revision numbers;
the version string alone is not a rollback identity.

## 9. AppImage status

An AppImage is a separate bundling project, not another package-manager recipe.
This application depends on Python, PyGObject, GTK4, and libadwaita. A
production AppImage must include or reliably locate a compatible Python/GTK
runtime, desktop file, icon, and launch wrapper without loading host package
manager libraries unsafely.

Do not publish the current AppImage placeholder as a portable executable. First
choose and test a bundling design, then validate it on supported distributions
and architectures, generate a detached signature, and publish the AppImage and
checksum together. Until that work is complete, native packages and Flatpak
are the supported desktop distribution paths.

## 10. Software-center integration

GNOME Software, KDE Discover, and similar clients display applications from
the configured package/Flatpak repositories and their AppStream metadata.
Installing a `.deb` or `.rpm` once does not create a store listing.

For native stores, ensure the repository contains:

- signed package files;
- signed `Release`/Yum repository metadata;
- correct dependency declarations;
- a desktop file;
- a matching AppStream MetaInfo file;
- icons and screenshots where the target store requires them;
- a stable HTTPS project/support URL.

For Flatpak, the repository/AppStream catalog is produced as part of the
Flatpak build and is normally supplied by Flathub. For Snap, store metadata is
managed through the Snap Store listing and the snap’s `snapcraft.yaml`.

## 11. CI/CD layout

Use a tag-triggered release workflow with separate jobs, not one host build
that claims every distribution:

```text
tag vX.Y.Z
  ├─ quality: Rust tests, fmt, Clippy, GUI/Xvfb, security/audit checks
  ├─ deb: pinned Debian/Ubuntu builder, amd64 + arm64
  ├─ rpm: Fedora/Mock or Copr, each target chroot and architecture
  ├─ arch: clean Arch builder, x86_64 + supported ARM builder
  ├─ flatpak: Flathub-compatible builder and flatpak-builder-lint
  ├─ snap: Snapcraft builder for each architecture
  ├─ evidence: SHA256SUMS, MANIFEST.json, full Cargo SBOM, package reports
  └─ publish: protected manual approval, signing, channel/repository upload
```

Pull requests should build and lint without access to signing keys or store
credentials. Store publication should run only from a protected tag workflow
after a human reviews the exact commit, artifact hashes, package contents, and
release notes.

Never store GPG private keys, Snapcraft login files, Flatpak signing keys,
cloud credentials, or package-store tokens in this repository or in ordinary
CI logs.

## 12. Verification and rollback checklist

### Before publication

- [ ] Public repository, domain, ID, maintainer, email, and license are final.
- [ ] `LICENSE`, copyright, changelog, support URL, and security contact exist.
- [ ] Tag points to the exact reviewed commit.
- [ ] Rust tests, format, Clippy, provider contracts, GUI smoke, and release
      audit pass.
- [ ] Each package is built in the correct clean target environment.
- [ ] `.deb` passes `lintian`; RPM passes `rpmlint`; Arch passes `namcap`.
- [ ] Flatpak manifest/repository lints pass; screenshots and license paths are
      present; Flathub ID/domain rules are satisfied.
- [ ] Snap passes automated review, has the correct grade/confinement, and any
      classic approval is recorded.
- [ ] Install, upgrade, launch, scan, history/cache, and safe plan-preview
      tests pass on disposable VMs.
- [ ] Real Polkit authorization and mutation tests pass only in disposable
      environments.
- [ ] Checksums, SBOM, signatures, and artifact manifests are archived.

### Rollback

- Debian/APT: keep the previous package and repository metadata; restore the
  previous version and verify `apt update`/install on a clean VM.
- RPM/DNF: retain the previous RPM/SRPM and repository snapshot; restore the
  previous repository state or use the exact previous version with DNF.
- Arch: keep the previous package/recipe commit and restore the previous AUR
  or repository version.
- Flatpak: identify the previous remote commit with `flatpak remote-info --log`
  and deploy that known-good commit when a rollback is required.
- Snap: keep the previous store revision and use the Snap Store channel map or
  `snap revert --revision` on affected systems.
- In every case, stop the rollout first, preserve logs and hashes, communicate
  the reason, and only republish after a corrected artifact passes the same
  gates.

## Official references

- Debian packaging workflow: <https://www.debian.org/doc/manuals/debmake-doc/ch06.en.html>
- Fedora RPM packaging and Mock: <https://developer.fedoraproject.org/deployment/rpm/about.html>
- Arch package creation: <https://wiki.archlinux.org/title/Creating_packages>
- Arch User Repository: <https://wiki.archlinux.org/title/Arch_User_Repository>
- Flatpak build: <https://docs.flatpak.org/en/latest/first-build.html>
- Flathub requirements: <https://docs.flathub.org/docs/for-app-authors/requirements>
- Flathub submission: <https://docs.flathub.org/docs/for-app-authors/submission>
- Flathub MetaInfo guidelines: <https://docs.flathub.org/docs/for-app-authors/metainfo-guidelines>
- Snap build: <https://snapcraft.io/docs/create-a-new-snap/>
- Snap authentication: <https://snapcraft.io/docs/snapcraft-authentication/>
- Snap publishing: <https://snapcraft.io/docs/releasing-your-app/>
- Snap channels and tracks: <https://snapcraft.io/docs/explanation/how-snaps-work/channels-and-tracks/>
