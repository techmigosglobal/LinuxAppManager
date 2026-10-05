# VIN-LinuxManager publishing runbook

This runbook is the practical sequence for publishing VIN-LinuxManager after
the first public release. It separates artifact stores from software centers
that index package repositories and AppStream metadata.

## Current status

Already public:

- Repository: `https://github.com/techmigosglobal/LinuxAppManager`
- Application ID: `io.github.techmigosglobal.LinuxAppManager`
- Website: `https://techmigosglobal.github.io/LinuxAppManager/`
- GitHub release: `v0.1.0`
- Native artifact: `linux-app-manager_0.1.0_amd64.deb`
- Release checksums: `SHA256SUMS`

Still to publish:

- Snap Store
- Flathub
- Debian/Ubuntu APT repository or PPA
- Fedora/Copr or openSUSE/OBS repository
- Arch User Repository
- AppImage

Before any store submission, replace the provisional maintainer email in
`debian/control`, `debian/changelog`, and the RPM metadata, confirm the legal
license, add a `LICENSE` file, and decide which architectures are supported.
The current GitHub release has checksums but is not GPG-signed.

## 1. Prepare each release

Use a clean checkout and keep the release tag immutable:

```bash
git clone https://github.com/techmigosglobal/LinuxAppManager.git
cd LinuxAppManager
git fetch --tags --prune
git show --stat v0.1.0

export VERSION=0.1.0
export TAG="v${VERSION}"
export RELEASE_COMMIT="$(git rev-list -n1 "$TAG")"
```

Run the quality gates before every new tag:

```bash
RUSTUP_TOOLCHAIN=1.90.0 cargo fmt --all -- --check
RUSTUP_TOOLCHAIN=1.90.0 cargo test --all-targets
RUSTUP_TOOLCHAIN=1.90.0 cargo clippy --all-targets -- -D warnings
./scripts/test-integration.sh
./scripts/release-audit.sh
./scripts/verify-package-recipes.sh
```

Create and push a tag only after the exact commit has been reviewed:

```bash
git tag -a "v${VERSION}" -m "VIN-LinuxManager ${VERSION}"
git push origin "v${VERSION}"
```

Keep hashes, SBOMs, package reports, and builder details with the release. Do
not put store tokens, GPG private keys, or Snapcraft credential files in Git.

## 2. Snap Store

The Snap Store receives a built `.snap` and assigns a store revision.

### 2.1 Resolve confinement first

The current [`snap/snapcraft.yaml`](../snap/snapcraft.yaml) is development-only
(`grade: devel`) and requests `confinement: classic`.

Before stable publication:

1. Test whether inventory works with strict confinement and only the required
   interfaces.
2. If classic is genuinely required, document why and request classic review.
3. Change `grade` to `stable` only after confinement and clean-host tests pass.
4. Keep the existing runtime guard that disables host package mutation in a
   sandboxed build.

### 2.2 Register and build

```bash
sudo snap install snapcraft --classic
snapcraft --version
snapcraft login
snapcraft whoami
snapcraft register linux-app-manager
snapcraft clean
snapcraft pack
```

Build and test every supported architecture. Do not claim `arm64` support
until a real arm64 build has been installed and tested.

### 2.3 Upload, test, and promote

Start with `edge`:

```bash
snapcraft upload --release=edge linux-app-manager_0.1.0_amd64.snap
snap info linux-app-manager
```

On a separate clean host, install using the command shown by the store (a
classic snap may require `--classic`), then test launch, inventory, provider
health, history, and sandbox mutation behavior:

```bash
sudo snap install linux-app-manager --edge
snap run linux-app-manager
snap list linux-app-manager
```

Promote the exact tested revision:

```bash
snapcraft release linux-app-manager <REVISION> candidate
snapcraft release linux-app-manager <REVISION> stable
```

Record the revision and store URL. The revision is the rollback identity:

```bash
sudo snap revert linux-app-manager
```

## 3. Flatpak and Flathub

Flathub accepts a manifest and source metadata through a GitHub pull request;
it is not a binary upload store.

### 3.1 Build locally

```bash
flatpak remote-add --if-not-exists --user flathub \
  https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install -y flathub org.flatpak.Builder
```

Install `flatpak-cargo-generator.py` from the
`flatpak/flatpak-builder-tools` project, place it on `PATH`, then render from
the immutable release commit:

```bash
export LAM_SOURCE_URL="https://github.com/techmigosglobal/LinuxAppManager.git"
export LAM_SOURCE_COMMIT="$RELEASE_COMMIT"
mkdir -p dist/flatpak
./scripts/render-flatpak.sh dist/flatpak
```

Review the generated manifest and `cargo-sources.json`, then build and install:

```bash
flatpak-builder --force-clean \
  --user --install-deps-from=flathub \
  --repo=dist/flatpak/repo --install \
  dist/flatpak/builddir \
  dist/flatpak/io.github.techmigosglobal.LinuxAppManager.yml

flatpak run io.github.techmigosglobal.LinuxAppManager
flatpak run --command=flatpak-builder-lint org.flatpak.Builder \
  manifest dist/flatpak/io.github.techmigosglobal.LinuxAppManager.yml
flatpak run --command=flatpak-builder-lint org.flatpak.Builder \
  repo dist/flatpak/repo
```

Confirm that the GUI, inventory, history, icon, and metadata work, and that
destructive host operations remain disabled in the sandbox.

### 3.2 Submit to Flathub

Before submission, finalize the license, maintainer identity, screenshots,
AppStream metadata, icon, runtime branch, and source permissions:

```bash
appstreamcli validate \
  packaging/io.github.techmigosglobal.LinuxAppManager.metainfo.xml
```

Create the submission branch from Flathub’s `new-pr` branch:

```bash
gh repo fork flathub/flathub --clone
cd flathub
git checkout --track origin/new-pr
git checkout -b add-vin-linuxmanager new-pr
```

Copy only the final manifest and generated Cargo source metadata. Do not copy
`builddir`, `repo`, `.flatpak` bundles, or binaries. Open the pull request
against `flathub/flathub:new-pr` with a title such as:

```text
Add io.github.techmigosglobal.LinuxAppManager
```

Respond to review comments in the same PR. After requested fixes, comment
`bot, build` to start the Flathub test build. If accepted, enable GitHub 2FA,
accept the Flathub repository invitation, and maintain the new app repository.

## 4. Debian/Ubuntu and GNOME Software

GNOME Software has no separate upload portal. It reads package/Flatpak
backends and AppStream metadata.

### Option A: Ubuntu Launchpad PPA

1. Replace the provisional maintainer identity.
2. Add the final `LICENSE` and `debian/copyright`.
3. Convert the current native package to an archive-quality source package if
   Launchpad requires it.
4. Build a signed source upload for each Ubuntu series and architecture.
5. Upload the `.changes` file with `dput`.
6. Wait for Launchpad builds, then test the PPA on a clean Ubuntu VM.
7. Refresh GNOME Software and verify the name, icon, description, screenshots,
   install, update, and removal paths.

### Option B: Operate a signed APT repository

Build one package per supported series and architecture, then create signed
metadata with `reprepro` or `apt-ftparchive`:

```bash
sudo apt-get install --yes reprepro
reprepro -b /srv/vin-linuxmanager includedeb <suite> \
  /path/to/linux-app-manager_<VERSION>_<ARCH>.deb
```

Serve it over HTTPS. Publish the public key with a verified fingerprint and
configure clients with `signed-by=`. Ensure AppStream/DEP-11 metadata is
available to the repository backend:

```bash
sudo apt update
sudo apt install linux-app-manager
gnome-software
```

The existing GitHub `.deb` is a direct download, not an APT repository and not
yet a GNOME Software listing.

## 5. Fedora/RPM and GNOME Software

Build on a Fedora-compatible builder and test the exact target distribution:

```bash
sudo dnf install --yes \
  rpm-build rpmdevtools rust cargo gcc elfutils rpmlint \
  python3-gobject gtk4 libadwaita polkit
rpmdev-setuptree
git archive --format=tar.gz \
  --prefix="linux-app-manager-${VERSION}/" \
  --output="$HOME/rpmbuild/SOURCES/linux-app-manager-${VERSION}.tar.gz" \
  "$TAG"
cp rpm/linux-app-manager.spec "$HOME/rpmbuild/SPECS/"
rpmbuild -ba "$HOME/rpmbuild/SPECS/linux-app-manager.spec"
rpmlint "$HOME/rpmbuild/RPMS"/*/linux-app-manager-*.rpm
```

Copr is the simplest public Fedora route:

```bash
sudo dnf install --yes copr-cli
copr-cli create linux-app-manager --chroot fedora-rawhide-x86_64
copr-cli build linux-app-manager \
  "$HOME/rpmbuild/SRPMS/linux-app-manager-${VERSION}-*.src.rpm"
```

Select every real target chroot, wait for all builds, and test the generated
repository on a clean Fedora VM. Confirm that AppStream metainfo and both icon
formats are present. Copr is not official Fedora inclusion; that requires the
separate Fedora review and maintainer process. Use OBS for openSUSE targets.

## 6. Arch Linux

The normal community route is AUR. AUR publishes `PKGBUILD` and `.SRCINFO`,
not a prebuilt binary:

```bash
sudo pacman -S --needed base-devel rust cargo python-gobject gtk4 libadwaita polkit namcap
cd arch
makepkg --cleanbuild --syncdeps --rmdeps --check
namcap PKGBUILD
namcap linux-app-manager-*.pkg.tar.zst
```

After creating or obtaining the real AUR repository:

```bash
git clone ssh://aur@aur.archlinux.org/linux-app-manager.git aur-linux-app-manager
cp PKGBUILD aur-linux-app-manager/PKGBUILD
cd aur-linux-app-manager
makepkg --printsrcinfo > .SRCINFO
git add PKGBUILD .SRCINFO
git commit -m "linux-app-manager ${VERSION}"
git push
```

Use an immutable release source, verify dependencies and license, and test
upgrade/removal in a clean Arch environment. Official Arch repository
inclusion is a separate review process.

## 7. AppImage

AppImage is a portable artifact, not a universal store. Because the current
GUI depends on Python GTK/libadwaita, a real runtime-bundling design is needed
before publishing one.

When implemented:

1. Build against the oldest supported glibc baseline.
2. Bundle or reliably locate the Python/GTK runtime and required libraries.
3. Produce the AppImage with a maintained linuxdeploy/appimagetool pipeline.
4. Test on clean Ubuntu, Fedora, and Arch machines.
5. Publish the AppImage, checksum, detached signature, and update metadata
   together on GitHub Releases.
6. Optionally submit the verified release metadata to an AppImage directory.

Do not publish the current AppImage placeholder as an executable.

## 8. Evidence and rollback

For every channel, retain the source commit, artifact hash, builder environment,
install/launch/upgrade results, sandbox or confinement behavior, metadata/icon
check, store/repository URL, assigned build or revision ID, and rollback
command.

Promote gradually: local/private test, edge or beta, candidate, then stable.
Keep the previous release available until the new one passes a clean-host
smoke test. If a defect appears, stop promotion, preserve logs and hashes,
revert to the previous channel revision, and resume only after the corrected
artifact passes the same gates.

## Official documentation

- Flathub requirements: <https://docs.flathub.org/docs/for-app-authors/requirements>
- Flathub submission: <https://docs.flathub.org/docs/for-app-authors/submission>
- Flatpak first build: <https://docs.flatpak.org/en/latest/first-build.html>
- Snap authentication: <https://snapcraft.io/docs/snapcraft-authentication/>
- Snap publishing: <https://snapcraft.io/docs/releasing-your-app/>
- Snap channels: <https://snapcraft.io/docs/explanation/how-snaps-work/channels-and-tracks/>
- Arch AUR: <https://wiki.archlinux.org/title/Arch_User_Repository>
- GNOME Software metadata: <https://github.com/GNOME/gnome-software/blob/main/doc/app-developers.md>
- Debian repository setup: <https://wiki.debian.org/DebianRepository/SetupWithReprepro>
