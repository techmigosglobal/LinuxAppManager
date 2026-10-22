# Install VIN-LinuxManager

Version 0.1.0 is public on [GitHub Releases](https://github.com/techmigosglobal/LinuxAppManager/releases/tag/v0.1.0).
Version 0.1.1 and its new distribution channels are staged until the checks in
[PUBLISHING_STATUS.md](PUBLISHING_STATUS.md) pass. The repository commands below
are for use **after that channel is marked published**; a source recipe alone
does not make a package available.

## Ubuntu 24.04 / 26.04 and Debian 13 (amd64)

Each release is built on the matching distribution. Do not install the Ubuntu
26.04 build on Ubuntu 24.04 or assume a derivative has been tested.

1. Download the repository's binary public key and inspect its fingerprint:

```sh
curl --fail --location --output vin-linuxmanager.gpg \
  https://techmigosglobal.github.io/LinuxAppManager/apt/vin-linuxmanager.gpg
gpg --show-keys --with-colons vin-linuxmanager.gpg
```

The primary key fingerprint must be
`DE6DC03A1F11C0176188BBAC6E75CBCE90CE3F16`. This is the existing release key;
its public certificate is also committed under `packaging/`. Stop if it differs.

2. Select exactly one suite: `ubuntu24.04`, `ubuntu26.04`, or `debian13`.
Download its `.sources` file, inspect it, and opt in explicitly. For Ubuntu 24.04:

```sh
curl --fail --location --output vin-linuxmanager.sources \
  https://techmigosglobal.github.io/LinuxAppManager/apt/vin-linuxmanager-ubuntu24.04.sources
cat vin-linuxmanager.sources
sudo install -d -m 0755 /etc/apt/keyrings
sudo install -m 0644 vin-linuxmanager.gpg /etc/apt/keyrings/vin-linuxmanager.gpg
sudo install -m 0644 vin-linuxmanager.sources /etc/apt/sources.list.d/vin-linuxmanager.sources
sudo apt update
sudo apt install linux-app-manager
linux-app-manager
```

The source must use HTTPS, `Architectures: amd64` and
`Signed-By: /etc/apt/keyrings/vin-linuxmanager.gpg`. No `apt-key`, global trust,
or `trusted=yes` is needed. Subsequent updates use normal APT commands.

The repository retains the newest two compatible versions per suite. Inspect
`apt-cache policy linux-app-manager`, then roll back with
`sudo apt install --allow-downgrades linux-app-manager=VERSION` if necessary.
The first multi-suite release has no compatible predecessor yet.

Remove the app with `sudo apt remove linux-app-manager`. Remove the specific
`.sources` and keyring files to stop receiving repository updates. Local user
history is separate from package installation.

## Fedora 43 / 44 (x86_64)

Download the RPM for your Fedora release and its detached signature from the
same signed GitHub release. Verify its SHA-256 checksum and GPG signature using
the fingerprint above, then install with `sudo dnf install ./PACKAGE.rpm`.
An RPM built for one Fedora release is not advertised for another.

Copr publication requires the maintainer's Fedora/Copr account. No Copr project
or installation command is claimed until its build and repository URL are
verified. Direct RPM downloads and Copr availability are tracked separately.

## Arch Linux (x86_64)

The release includes `linux-app-manager-VERSION-aur.tar.gz` with a concrete
`PKGBUILD` and `.SRCINFO`, generated from the immutable vendored source archive
and its actual SHA-256 digest. Review the files and build as an unprivileged
user with `makepkg --syncdeps --install`. AUR publication requires the
maintainer's AUR account and SSH access; do not infer it from the recipe bundle.

## AppImage

Only a release which includes a verified `VIN-LinuxManager-VERSION-x86_64.AppImage`
offers this route. Verify the signed checksums, make the file executable and run
it. `./FILE.AppImage --appimage-extract` followed by `./squashfs-root/AppRun`
provides operation without FUSE. Production builds use Ubuntu 24.04 and bundle
Python/GTK; package-manager subprocesses use the host environment.

## Store discovery

An opt-in APT/Copr repository does not add the app to every default store.
Ubuntu App Center's documented Debian search uses the official Ubuntu archives.
Fedora's `fedora` Flatpak remote and Flathub are distinct. Snap and Flatpak
packages have their own reviews and currently refuse host package changes.

Official references: [Ubuntu package formats](https://ubuntu.com/desktop/docs/en/24.04/explanation/snap-and-deb-packages/),
[Fedora Flatpak remotes](https://developer.fedoraproject.org/deployment/flatpak/flatpak-usage.html).
