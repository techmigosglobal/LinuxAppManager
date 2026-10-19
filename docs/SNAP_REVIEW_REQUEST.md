# Snap eligibility review draft

Prepared 2026-10-19. This is a maintainer review draft, not a posted request or
an assertion that classic confinement is approved.

## Proposed forum topic

Eligibility guidance for vin-linux-app-manager: read-only host package inventory

## Proposed request

Snap name: `vin-linux-app-manager`  
Publisher: `techmigos` (upstream publisher)  
Upstream: https://github.com/techmigosglobal/LinuxAppManager  
Listing: https://snapcraft.io/vin-linux-app-manager

VIN-LinuxManager is a GTK4/libadwaita utility for viewing installed applications,
package details, provider health, duplicate installations and local history.
Native packages support reviewed package removal; the Snap edition explicitly
disables host removal and cleanup in both the CLI and GUI. There is no privileged
host helper in this release.

The uploaded candidate is revision **3**, version **0.1.1**, amd64, core24,
classic/devel. The upload returned `(NEEDS REVIEW) confinement 'classic' not
allowed`, so no channel is released. It bundles Python, GTK,
libadwaita and the Rust executable. It queries host package-manager programs and
metadata to report the host inventory, including distro packages, Snap, Flatpak,
AppImage and other supported providers. The host commands run with host library
and Python environment settings rather than bundled runtime settings.

We understand that the classic-confinement guidance lists management snaps and
third-party installers among unsupported categories. We are not claiming that
this application belongs to an already supported classic category. Does the
read-only inventory edition qualify for reviewer consideration, or should we
pursue a narrower strict edition with separately reviewed metadata interfaces?

A strict build is not currently validated. Running the existing host queries in
a strict mount namespace would inspect the base or fail to find provider tools;
that must not be reported as the host inventory. A strict edition would need
provider-specific readers, narrowly scoped read-only access, accurate unavailable
states, and clean-host comparison tests. We will not use a broad host-execution
interface or enable host modifications to bypass this review.

The candidate has passed packed-file and installed-snapd CLI/GUI checks on
Ubuntu 24.04, including rejection of a host removal command. These automated
checks do not establish strict confinement eligibility, public store installation,
or clean desktop VM acceptance. Please advise on the supported publication route.

## Maintainer action

After reviewing this text, submit it to the
[classic-confinement category](https://forum.snapcraft.io/c/store-requests/classic-confinement/26)
and record the topic URL in PUBLISHING_STATUS.md.
Do not repeatedly upload the same package to work around a review hold.

Policy: https://snapcraft.io/docs/reference/administration/reviewing-classic-confinement-snaps/
