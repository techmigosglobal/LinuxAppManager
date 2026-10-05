# Distribution packaging

The detailed release workflow is in
[`docs/DISTRIBUTION_GUIDE.md`](../docs/DISTRIBUTION_GUIDE.md).

VIN-LinuxManager is a host package-management application. Native Debian,
RPM, and Arch packages are the authoritative operational artifacts because they
can access the host package databases and request Polkit authorization through
the desktop session.

Flatpak and Snap manifests are included as distribution starting points, but a
sandbox cannot safely manage every host package system. Before publishing a
sandboxed artifact, the release must either provide a reviewed host helper or
ship it as an inventory-only build with destructive controls disabled. Do not
advertise host uninstall support from a sandbox until that boundary is tested.

## Native package layout

Each native recipe installs:

- `lam` at `/usr/lib/linux-app-manager/lam`;
- the GTK frontend at `/usr/lib/linux-app-manager/app.py`;
- the launcher at `/usr/bin/linux-app-manager`;
- the desktop entry, AppStream metadata, and icon.

Build recipes:

- `debian/` for Debian/Ubuntu;
- `rpm/linux-app-manager.spec` for Fedora/openSUSE-style RPM builds;
- `arch/PKGBUILD` for Arch-based repositories;
- `snap/snapcraft.yaml` and `flatpak/*.yml.in` for sandboxed packaging review.

Before a store submission, confirm the maintainer/support metadata, build from
a clean tagged source archive, sign the package and checksum files, and run
`scripts/release-audit.sh`. On a Docker-enabled release workstation, run
`scripts/verify-clean-debian.sh` as well; it builds the Debian package in the
pinned Ubuntu image and rejects incomplete or contaminated package contents.
The RPM, Arch, Snap, and Flatpak recipes still require their respective
distro/store builders before publication.
