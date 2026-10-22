# Snap eligibility review draft

Updated 2026-10-22. This is a maintainer review draft, not a posted request or
an assertion that classic confinement is approved.

## Proposed forum topic

Eligibility guidance for vin-linux-app-manager: read-only host package inventory

## Proposed request

- name: `vin-linux-app-manager`
- description: Read-only GTK4/libadwaita inventory of host applications and packages.
- snapcraft: https://github.com/techmigosglobal/LinuxAppManager/blob/v0.1.1/snap/snapcraft.yaml
- upstream: https://github.com/techmigosglobal/LinuxAppManager
- upstream-relation: `techmigos`, the upstream publisher.
- supported-category: No supported classic category identified; requesting eligibility guidance for this read-only inventory utility.
- reasoning: The current provider implementation queries host package-manager tools and metadata. See the technical limitations below.

Listing: https://snapcraft.io/vin-linux-app-manager

I understand that strict confinement is preferred. A working strict prototype
and an interface trial have not been completed; the assessment below is based
on the current provider implementation. I am not claiming that existing
interfaces have already been proven insufficient.

VIN-LinuxManager is a GTK4/libadwaita utility for viewing installed applications,
package details, provider health, duplicate installations and local history.
Native packages support reviewed package removal; the Snap edition explicitly
disables host removal and cleanup in both the CLI and GUI. There is no privileged
host helper in this release.

The uploaded candidate is revision **4**, version **0.1.1**, amd64, core24,
classic/stable. The upload returned `(NEEDS REVIEW) confinement 'classic' not
allowed`, and the authenticated CLI still reported no released revisions on
2026-10-22. This candidate was built and tested from immutable tag `v0.1.1` at
`ccbd9a82e41f7fb314a69d3853ec2cb3c7190d63`. Its SHA-256 is
`009714f56d30c40f6633289862d96a0d45e95c22ae5ea15e4727471a1e9ab864`.
It bundles Python, GTK,
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

Request format: https://forum.snapcraft.io/t/about-the-classic-confinement-category/43830
