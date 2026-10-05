# Publication status

Updated: 2026-10-05

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

### Next Snap action from an interactive desktop terminal

Run this only after confirming the desktop session can read the existing
Snapcraft credentials:

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

The current manifest intentionally remains `grade: devel` and
`confinement: classic` until review and end-to-end testing are complete.
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

## GitHub source state

The source and publication metadata in this checkout are pushed to the
`main` branch of the [LinuxAppManager repository](https://github.com/techmigosglobal/LinuxAppManager).
Generated Snap binaries and build logs remain outside Git history in the ignored
`dist/snap-builds/` directory; the store/release artifact is the appropriate
publication channel for those files.
