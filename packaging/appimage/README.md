# AppImage release build

Build the x86_64 image on a clean Ubuntu 24.04 runner, the oldest supported
Ubuntu base. It bundles Python, PyGObject, Cairo, GTK4, libadwaita, introspection
metadata, schemas, icons, MIME data, and their ELF dependencies. Host glibc and
GPU drivers remain external. Cairo rendering is the default to avoid shipping
driver libraries tied to a different kernel.

```sh
sudo apt-get install build-essential pkg-config python3 python3-gi python3-gi-cairo \
  python3-cairo gir1.2-gtk-4.0 gir1.2-adw-1 libgtk-4-1 libadwaita-1-0 \
  libgdk-pixbuf2.0-bin libglib2.0-bin adwaita-icon-theme hicolor-icon-theme \
  shared-mime-info desktop-file-utils appstream curl squashfs-tools zsync \
  xvfb dbus-x11
scripts/build-appimage.sh /path/to/vendored-release-source /path/to/output
```

Install the Rust toolchain declared in Cargo.toml first. Cargo runs offline with
the lockfile and uses the source directory's vendored Cargo configuration. Place
`CARGO_TARGET_DIR`, `CARGO_HOME`, and `TMPDIR` on a disk with sufficient room.
External AppImage tools and the embedded runtime use versioned URLs with SHA-256
pins in `tools.json`; the build tool cannot download an unpinned latest runtime.

Both the builder tool and produced AppImage are extracted without FUSE. The
extracted payload must pass real provider inventory and GTK window startup with
its bundled Python under Xvfb/D-Bus before any output is copied to the output
directory. Collected Rust THIRD_PARTY_LICENSES from the vendored release source are required
for production builds and installed under usr/share/licenses/linux-app-manager/third-party.
All runtime package licenses and an installed-package inventory are
included; builder metadata is also emitted alongside the image for signing.

```sh
./VIN-LinuxManager-0.1.1-x86_64.AppImage --appimage-extract
./squashfs-root/AppRun                 # GUI without FUSE
./squashfs-root/AppRun --cli providers --json
./squashfs-root/AppRun --cli list --json
```

The GUI keeps its bundled libraries. Its Rust child and all host package manager,
cleanup, and Polkit subprocesses use host library/Python paths and retain the
user's PATH, display, D-Bus, home, and runtime directory. Native package behavior
is unchanged. The runtime does not enable sandbox restrictions or disable host
features; existing Snap/Flatpak mutation restrictions remain enforced.

`LAM_APPIMAGE_ALLOW_UNSUPPORTED_BUILDER=1` enables a development smoke build on
another OS and marks its metadata as a development builder. Such an image must
not be published as a supported release. Successful startup on the build host
does not establish cross-distribution support. Clean Ubuntu/Fedora/Arch desktop
VM installation, authorization cancellation, disposable-package operations,
history, and uninstallation checks remain required before those distributions
are advertised as supported.

Format follows the [AppDir specification](https://docs.appimage.org/reference/appdir.html)
and [manual packaging guidance](https://docs.appimage.org/packaging-guide/manual.html).
