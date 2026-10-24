# Publication status

Updated: 2026-10-24

## v0.1.1 implementation and verification

The native-first publishing implementation is prepared: six distro builders,
offline vendored sources, signed draft releases, a signed three-suite APT
repository, combined Pages deployment, a checksummed AUR recipe renderer and
an optional Python/GTK AppImage. The existing signed `v0.1.0` remains public.

New channels are **not yet claimed as publicly installable**. The release
workflow has a nonpublishing preflight mode and creates drafts for official
tags until clean-desktop installation acceptance is recorded.

Local evidence on 2026-10-19:

- All Rust tests, formatting and Clippy passed.
- 36 publishing-tooling tests passed, including real temporary GPG signatures,
  tamper rejection, deterministic source archives, native recipe contracts,
  AppImage subprocess isolation, retained package versions, and an isolated
  APT client downloading the previous version from a signed test repository.
- Dependency license collection verified 31 vendored crates and preserved 64
  exact upstream license/notice files for inclusion in native packages.
- Pacman inventory now uses its supported installed-package query; the old
  transaction-only option was rejected by real Pacman. Parser and isolated
  real-Pacman regression checks passed.
- GUI state/accessibility checks passed under Xvfb; sandboxed GUI state passed
  with both `FLATPAK_ID` and `SNAP`. These are automated checks, not desktop VM
  acceptance.
- The local vendored archive resolved all dependencies offline with an empty
  Cargo cache; it is a development snapshot, not an immutable tagged release.
- Recipe, desktop entry and AppStream validation passed. Actual target-builder
  installation logs are required separately.

Hosted builder evidence:

- [PR #1](https://github.com/techmigosglobal/LinuxAppManager/pull/1) is merged.
  Immutable tag `v0.1.1` resolves to
  `ccbd9a82e41f7fb314a69d3853ec2cb3c7190d63`; `v0.1.0` is preserved.
  The [official release run](https://github.com/techmigosglobal/LinuxAppManager/actions/runs/39800422189)
  passed source validation, all six native builds, runtime installation checks,
  AppImage extraction/launch, signed APT integration on all three suites and
  production signing. It created a 98-asset signed draft. The
  [tagged Snap run](https://github.com/techmigosglobal/LinuxAppManager/actions/runs/39800428550)
  passed the stable-grade Snap build and installed-snapd checks from that same
  immutable source: 1,252 host packages inventoried, bundled GUI launched and
  host removal refused. These remain automated checks, not desktop VM acceptance.
- Download verification found GitHub changed `~` to `.` in Debian asset names
  after signing. [PR #2](https://github.com/techmigosglobal/LinuxAppManager/pull/2)
  fixed future upload normalization and hosted filename/size/digest checks.
  The [draft metadata repair](https://github.com/techmigosglobal/LinuxAppManager/actions/runs/39805919359)
  passed: every original signature and package checksum was verified before
  re-signing the corrected manifest/checksum list. Nine download paths were
  corrected; the immutable tag and all 47 artifact content hashes are unchanged.
  Downloaded metadata signatures and the exact 98-asset hosted inventory were
  independently verified against the committed production public key,
  fingerprint `DE6DC03A1F11C0176188BBAC6E75CBCE90CE3F16`.
- Signed installation evidence from the official draft was downloaded and
  verified: GUI/inventory/uninstall success markers exist for all six native
  targets, and generated signed APT installation passed all three suites.
  The native release remains an installation-acceptance draft. Clean desktop
  VM checks, normal AppImage/FUSE launches and public repository installation
  have not been established by these container/Xvfb checks.
- [Pages deployment](https://github.com/techmigosglobal/LinuxAppManager/actions/runs/39803466814)
  stopped before deployment because no complete signed multi-suite native
  release is public. This preserves the existing website; production APT is
  not claimed as deployed. Dispatch Pages after desktop acceptance and draft
  promotion.
- [Corrected native preflight](https://github.com/techmigosglobal/LinuxAppManager/actions/runs/39263702994)
  passed all six builds and package audits, plus fresh-container installation,
  real asynchronous GUI startup/inventory, sandbox refusal checks and uninstall.
  Per-target success markers were inspected, rather than relying only on job
  conclusions. Fedora's Cairo typelib/GLES dependencies and pipeline failure
  propagation are fixed.
- The same run passed signed APT installation and removal for Ubuntu 24.04,
  Ubuntu 26.04 and Debian 13. Its signing key was an ephemeral test key, not
  the production repository key. Public repository deployment is still pending.
- [Snap installed-runtime validation](https://github.com/techmigosglobal/LinuxAppManager/actions/runs/39261014478)
  passed packed-file checks and an actual `snap install --dangerous --classic`
  on Ubuntu 24.04. `snap run` inventoried 1,250 packages, opened the bundled GUI,
  and refused host removal. This is automated runner evidence, not clean desktop
  VM or public store installation acceptance.
- The Snap uses the portable Python 3.12/GTK4/libadwaita runtime, relocated
  launch paths and core24 loader. Packaging pins patchelf 0.16.1 by SHA-256;
  newer versions reproduced a Python loader crash and are not used for this build.

Current account/store boundaries:

- On 2026-10-24 the authenticated forum displayed
  [Account temporarily on hold](https://forum.snapcraft.io/t/account-temporarily-on-hold/53771).
  It permits browsing but prevents replies and new topics pending staff review.
  This is an account moderation notice, not approval of the submitted request,
  classic confinement, or strict interfaces. Do not duplicate the held request
  or use another account to bypass the restriction. Native release acceptance
  continues independently on `main`.
- Forum authentication is now verified for `techmigos5`. On 2026-10-23 the
  authorized request was submitted in `snapcraft`, emphasizing a strict,
  read-only inventory edition and asking about appropriate PackageKit/metadata
  interfaces. The forum displayed **Post Needs Approval**, with **1 post
  pending**. There is no public topic URL or interface approval yet. See
  [the submitted strict guidance request](SNAP_STRICT_REQUEST.md). Do not
  duplicate the submission while moderation is pending.
- Strict is the alternative under assessment, not a validated production build.
  Current command-based providers require changes to avoid querying the snap
  base as if it were the host. Privileged interfaces can still need review.
  Host changes remain disabled; the current production manifest and uploaded
  revision 4 have not been changed or re-uploaded by this assessment.
- Desktop-session keyring access restored authenticated Snapcraft CLI access
  for publisher `techmigos`. The listing title, Utilities category, read-only
  description, website, GPL-3.0-or-later license, icon and three screenshots
  were saved and verified after reload.
- Revision **4**, `0.1.1` amd64/core24, `classic/stable`, was uploaded once with
  `--release=edge` on 2026-10-22. The store still returned `(NEEDS REVIEW)
  confinement 'classic' not allowed`; an authenticated status check reported
  no released revisions. Its source is the immutable `v0.1.1` commit above.
  SHA-256: `009714f56d30c40f6633289862d96a0d45e95c22ae5ea15e4727471a1e9ab864`.
  Candidate 4 and its report are retained in ignored `dist/snap-builds/0.1.1-tag/`.
- Historical revision **3**, a `0.1.1` amd64 candidate, was uploaded once with `--release=edge` on
  2026-10-19. The store returned `(NEEDS REVIEW) confinement 'classic' not allowed`.
  No edge, candidate or stable publication is claimed. On 2026-10-21 a release
  attempt returned `resource-not-ready: Snap cannot be published due to
  inconsistent state`. Maintainer-reported forum approval has not yet been
  verified as approval of this snap's classic confinement. On 2026-10-22 the
  authenticated CLI still reported no released revisions. The forum session
  was logged out then; sign-in and the strict guidance submission are now
  recorded above.
- Candidate SHA-256: `b0189975685706da57f4b94806573271504c8bfdb98da430cb1824145e518eb9`.
  Its embedded source commit is `b2c643521f4bbf12df571823d8152caefc2f88d8`
  (the PR merge commit built by the linked Snap validation run).
- The [prepared eligibility request](SNAP_REVIEW_REQUEST.md) acknowledges that
  Canonical lists management snaps as unsupported for classic confinement.
  A strict edition is not validated: existing host queries would need explicit
  metadata access and provider-specific changes to report actual host inventory.
  Revision 3 used `grade: devel` and cannot enter candidate/stable. Revision 4
  uses `grade: stable` and passed installed-runtime validation. Reviewer approval
  and public edge installation remain required before promotion. Do not retry
  this unchanged package to work around the review hold.
- No configured Copr credentials or verified Copr project were found. AUR
  publication also requires a maintainer account and authenticated repository.
- Flathub policy review is required before submission. Its current requirements
  exclude host utilities/host-dependent core functionality and prohibit
  AI-assisted manifests and AI-driven submission interactions. The existing
  Flatpak template has not been rewritten or submitted by this implementation.
- Fedora Flatpak inclusion and default Ubuntu/Fedora archive discovery are
  separate maintainer reviews, not side effects of APT/Copr publication.

Use [PUBLISHING_V0.1.1.md](PUBLISHING_V0.1.1.md) for the current release,
acceptance, promotion and rollback procedure, and [INSTALL.md](INSTALL.md) for
installation instructions after a channel becomes public.

## Historical v0.1.0 attempts (2026-10-05)

This file records the publication attempts and the remaining human/store-side
actions for VIN-LinuxManager. It is intentionally factual: a successful local
build or a registered store name is not the same as a published release.

## Snap Store

- Registered snap name: `vin-linux-app-manager`.
- The Snap Store account registration and interactive `snapcraft login` /
  `snapcraft whoami` check succeeded for the publisher account.
- Launchpad remote build completed successfully for `amd64` using the
  `core24` base.
- Verified artifact: `dist/snap-builds/vin-linux-app-manager_0.1.0_amd64.snap`.
- Verified SHA-256:
  `963ada7a63e9cc233af2a0f3103115d4845d7256173e04d01c4588d61c7930f6`.
- Verified embedded metadata: name `vin-linux-app-manager`, version `0.1.0`,
  architecture `amd64`, and the 512px application icon.
- The latest upload attempt from the Codex execution shell did not reach the
  store because Snapcraft could not access the desktop keyring (`No keyring
  found to store or retrieve credentials from`). The generated artifact is
  preserved under `dist/snap-builds/`; it is not committed to the source
  repository.
- The earlier store response also flagged `classic` confinement for manual
  review. Therefore no edge or stable revision is claimed as published.

### Historical command (superseded by the 0.1.1 upload above)

Do not rerun this old upload. It is retained only as historical context:

```sh
cd /home/vinay/Documents/linux-app-manager-core/linux-app-manager
snapcraft upload --release=edge ./dist/snap-builds/vin-linux-app-manager_0.1.0_amd64.snap
```

If the store again requests classic-confinement review, open a topic in the
[classic-confinement forum category](https://forum.snapcraft.io/c/store-requests/classic-confinement/26)
with the snap name, public Snapcraft URL, upstream URL, publisher relation,
supported category, and a narrow technical justification. Explain that the
application inventories and manages host package-manager sources and needs
host provider access. Do not claim approval in advance; the store may require
a strict-confinement redesign instead.

Historical revision 3 used `grade: devel`. The next packaging manifest uses
`grade: stable`; confinement remains `classic` and still requires store approval.
A stable grade does not itself approve or publish the snap.
See the [official classic-confinement review guidance](https://snapcraft.io/docs/reviewing-classic-confinement-snaps/).

## Flathub

- The Flatpak manifest, Cargo source metadata, desktop file, icons, and
  license material have been prepared previously in the ignored
  `dist/flathub-submission/` bundle.
- No Flathub pull request was created by this run. The bundle must be refreshed
  to the current source commit before submitting it through the Flathub
  repository workflow, then reviewed by the maintainer and Flathub reviewers.
- A Flathub submission is separate from Snap Store publication and should not
  be described as complete until the pull request is merged and the first
  build is available in Flathub.

## Current source and artifact state

The implementation was merged through
[PR #1](https://github.com/techmigosglobal/LinuxAppManager/pull/1) and tagged
[`v0.1.1`](https://github.com/techmigosglobal/LinuxAppManager/tree/v0.1.1).
The signed native draft is built and its download metadata is verified; public
installation acceptance is still pending. Revision 4 and its builder report are
retained in ignored `dist/snap-builds/0.1.1-tag/`; historical revision 3 is kept
separately in `dist/snap-builds/0.1.1/`. Credentials and private signing keys are
not included.
