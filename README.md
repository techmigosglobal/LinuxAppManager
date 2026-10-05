# VIN-LinuxManager

VIN-LinuxManager is a focused Linux software manager built around a Rust library (`lam_core`),
the `lam` CLI, and a GTK4/libadwaita desktop interface. `linux-app-manager` remains
the stable technical package name for upgrade compatibility.

## Done
- Unified `InstalledApplication` model, `PackageProvider` trait (no generic run-command API)
- Providers: APT/dpkg, DNF/RPM, Pacman, Flatpak apps and runtimes, Snap, AppImage, and manual desktop launchers (with provider-specific safety boundaries)
- .desktop discovery + package↔app linking, classifier (apps vs libraries/system/kernel)
- Safety: strict package-id/path validation, protected-package rules, APT, DNF, and Pacman transaction previews, exact RPM and Flatpak references, and recoverable AppImage removal through Trash
- Duplicate detection across sources; CLI: providers, list, search, info, duplicates, history, cache, cleanup, and plan-remove
- Desktop GUI: searchable desktop-application inventory, full-package inventory, duplicate view, provider-health warnings, package details, confirmed removal, operation history, and a live transaction log

## Deliberate release boundaries

1. `lam cleanup NAME --yes` only moves a known Flatpak user-data directory to
   the desktop Trash after re-validating its canonical path. Unknown leftovers,
   Snap data, and manual launchers remain inspection-only.
2. Flatpak and Snap store builds are inventory/history builds until a reviewed
   host-helper boundary exists; both the GUI and CLI refuse host mutations when
   `FLATPAK_ID` or `SNAP` is present.
3. A dedicated D-Bus helper and a self-contained Python/GTK AppImage are still
   release follow-ups. Native packages and the Flatpak template remain the
   supported distribution paths until those boundaries are completed.

AppImage discovery is limited to explicit application roots and user-owned
AppImages are moved to Trash rather than permanently deleted. Manual desktop
launchers are visible but remain non-removable until their underlying ownership
can be proven.

APT and DNF operations request authorization through Polkit; Flatpak and Snap use their own system authorization. Each removal requires a separate GUI confirmation, recomputes the package manager's transaction, blocks protected packages, and checks that the transaction still matches the reviewed preview. The GUI streams package-manager output into a modal progress window.

Run the desktop GUI with `./run-gui`. It builds the Rust CLI and opens the GTK window. The **Applications** view shows desktop applications only; CLI tools, libraries, runtimes, and system components are available in **All packages**. Provider availability and scan health are shown in the scan summary. On RPM systems, the inventory is populated from the RPM database when it is readable by the current session.

Build the CLI with `cargo build --release --locked` · Try: `target/release/lam list`

## Website

The static product website lives in [`website/`](website/). Preview it with
`python3 -m http.server 4173 --directory website`; the GitHub Pages workflow
publishes it from `main` after the repository’s Pages setting is enabled.

## Support

- Website: <https://techmigos.com>
- Support: <mailto:Vin-Linux-App-Manager@techmigos.com>
- Issues: <https://github.com/techmigosglobal/LinuxAppManager/issues>
