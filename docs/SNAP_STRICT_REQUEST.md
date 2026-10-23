# Strict Snap guidance request

Submitted 2026-10-23 using the signed-in forum account `techmigos5`.
Category: `snapcraft` (packaging guidance, not a claim of interface approval).
The forum confirmed **Post Needs Approval**, with **1 post pending**. No public
topic URL was provided. Do not create a duplicate while moderation is pending.

Strict confinement is the alternative being assessed. It needs provider changes
and genuinely confined host-inventory tests; the production manifest remains
classic until a useful replacement is validated. Devmode cannot provide a
stable/searchable store release. Privileged strict interfaces may still need
separate approval and must not be described as automatically granted.

References checked on 2026-10-23:

- [Confinement levels](https://snapcraft.io/docs/explanation/security/snap-confinement/)
- [PackageKit permissions](https://snapcraft.io/docs/reference/interfaces/packagekit-control-interface/)
- [System-file ownership restrictions](https://snapcraft.io/docs/reference/interfaces/system-files-interface/)
- [Classic review policy](https://snapcraft.io/docs/reference/administration/reviewing-classic-confinement-snaps/)

## Topic

Strict confinement guidance for vin-linux-app-manager: read-only host inventory

## Body

We maintain VIN-LinuxManager, published under the Snap publisher `techmigos`
with snap name `vin-linux-app-manager`. We would like to pursue a useful,
strictly confined, read-only host application inventory edition.

Upstream: https://github.com/techmigosglobal/LinuxAppManager

Current manifest: https://github.com/techmigosglobal/LinuxAppManager/blob/v0.1.1/snap/snapcraft.yaml

Our classic/stable candidate, revision 4 (0.1.1, core24, amd64), was uploaded on
22 October and returned `(NEEDS REVIEW) confinement 'classic' not allowed`.
We understand that the classic guidance lists management snaps as unsupported.
This topic asks about a legitimate strict route; it does not assert classic or
interface approval.

The existing Rust providers invoke `dpkg-query`, `rpm`, `pacman`, `snap list`
and `flatpak list`. Those implementations would need to change: shipping the
tools inside a strict snap and querying the base's package database must not
be presented as the host's inventory. AppStream metadata could enrich results,
but we would also need a reliable way to determine what is actually installed.

The proposed Snap scope is viewing installed packages/applications, versions,
provider health and duplicate installations where supported. Host removal and
cleanup are already disabled in both CLI and GUI and will remain disabled.
There is no privileged host helper. A working strict prototype and interface
trials have not yet been completed.

Could you advise on these points before we change the production manifest?

1. Is read-only installed-package enumeration through the host PackageKit
   service an appropriate strict approach? `packagekit-control` appears broader
   than our needs and does not normally auto-connect. Is there a narrower
   supported route, or a review process appropriate to this read-only use?
2. If PackageKit is unavailable or lacks a suitable backend, which approved
   host metadata interfaces, if any, would suit this utility? We do not assume
   arbitrary distro package databases qualify for `system-files`; the ownership
   restriction needs reviewer guidance.
3. For Snap/Flatpak inventory, is there a supported read-only approach without
   broad management permissions? We can limit the strict edition to supported
   providers and clearly report the others as unavailable.

We are not proposing `snapd-control`, `system-backup`, broad host execution or
host modification as a way around confinement. Native packages can continue
to provide the full management features. Any strict candidate would need
comparison against actual host inventory and denial/absence tests before
publication. Thank you for guidance on an acceptable implementation route.
