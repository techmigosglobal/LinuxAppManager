# Linux App Manager productionization plan

## Goal

Turn Linux App Manager into a trustworthy, distributable desktop application for
Linux users. The release must never imply that a package source was scanned when
it was only detected, and destructive actions must remain provider-specific,
reviewable, and rechecked immediately before execution.

## Phase 1: trustworthy inventory (current slice)

- [x] Expose provider health separately from provider availability.
- [x] Keep failed providers visible in JSON and the GUI with actionable status.
- [x] Make the default Applications view desktop applications; keep CLI tools in
      All packages.
- [x] Remove strict Clippy failures.
- [x] Add deterministic tests for provider status and default filtering.

Acceptance: a failed provider is shown as unavailable/unhealthy, not as an
empty successful inventory; the default view does not list ordinary CLI tools;
`cargo test`, `cargo fmt --check`, and `cargo clippy -- -D warnings` pass.

## Phase 2: provider coverage and persistence

- [x] Add Pacman inventory and guarded removal support.
- [x] Add AppImage and manual-install discovery with canonical-path validation.
- [x] Add SQLite cache and append-only operation history.
- [x] Add leftover/cache sizing plus a guarded, recoverable cleanup action for
      provider-owned Flatpak user data.
- [x] Add provider contract tests using disposable fake package-manager binaries.

Acceptance: supported providers report scan, preview, and operation capability;
inventory survives an application restart; no cleanup action deletes outside an
explicit, validated ownership boundary.

## Phase 3: desktop quality

- [x] Add GUI integration smoke tests under Xvfb.
- [x] Add keyboard/focus/accessibility checks for navigation, search, details,
      removal preview, confirmation, and progress.
- [x] Add clear source-health and partial-scan states.
- [x] Add operation history and cache inspection; guarded Flatpak user-data
      cleanup uses the desktop Trash and other ambiguous leftovers remain read-only.

Acceptance: the critical GUI flows run in a disposable test session and all
destructive flows show the exact provider plan before authorization.

## Phase 4: distribution

- [x] Add reproducible Flatpak manifest template, desktop entry, metainfo, and icons.
- [x] Add Debian, RPM, Arch, and Snap build recipes; AppImage remains blocked on
      bundling the Python/GTK runtime.
- [x] Add pinned Ubuntu clean-builder verification for the Debian artifact.
- [ ] Add RPM, Arch, Snap, and AppImage clean-builder verification where the host
      platform and the final runtime bundling design can support them.
- [x] Add release audit and Flatpak rendering scripts.
- [x] Add release scripts that emit checksums, SBOM/dependency information, and
      a manifest of files and versions.
- [x] Document signing, review, rollback, and store-submission prerequisites.

Acceptance: CI can build and validate each declared artifact from a clean
checkout; no artifact contains source secrets, caches, signing material, or
user data. Store publication remains an external maintainer step.

## Verification checkpoints

1. After Phase 1: unit tests, formatting, Clippy, release build, JSON smoke.
2. After Phase 2: provider contract tests, persistence restart test, safety audit.
3. After Phase 3: Xvfb GUI smoke and accessibility review.
4. Before publication: clean-room builds, checksums, artifact inspection, and
   documented rollback procedure.

## Risks

| Risk | Mitigation |
| --- | --- |
| Package-manager output differs by distro/version | Keep parser fixtures per provider and fail closed on incomplete previews. |
| A package manager is installed but unusable in the current session | Report availability and health independently, with the original error. |
| Manual/AppImage ownership is ambiguous | Discover only explicit roots and disable removal until canonical ownership is proven. |
| Store packaging does not include Python GTK runtime | Make Flatpak the primary portable artifact and declare system dependencies for native packages. |
| Large feature work hides regressions | Land small slices with tests and a green checkpoint after each phase. |
