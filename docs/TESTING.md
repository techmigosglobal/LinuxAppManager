# Testing boundaries

## Automated gates

- Rust unit tests cover package parsing, classification, protected-package
  rules, provider command construction, AppImage path safety, cleanup scope,
  and SQLite cache/history restart behavior.
- `tests/cli_contract.rs` runs the compiled CLI against the current host and
  verifies provider-health JSON, invalid-removal rejection, and isolated state
  history access.
- `tests/gui_smoke.py` runs under Xvfb and exercises the Applications, All
  packages, provider-warning, and History state transitions without starting a
  package operation.
- `tests/gui_accessibility_smoke.py` checks GTK roles, focusability, search and
  refresh labels, navigation focus, and selected-row behavior.
- `tests/provider_contract.rs` runs provider scan and APT preview adapters
  against disposable fake binaries and asserts fixed argv/elevation contracts
  for all supported providers.
- `scripts/release-audit.sh` validates release inputs, AppStream XML, Python
  syntax, and credential-pattern hygiene.

## Deliberate non-claims

No automated test performs a real uninstall or accepts a live Polkit prompt.
Those are destructive host operations and require a disposable VM or test
machine with explicit operator approval. The suite validates fixed commands,
preview rechecks, protected-package rejection, canonical cleanup boundaries,
and sandbox mutation blocking. Before publication, run provider preview and
authorization checks on representative Debian/Ubuntu, Fedora/openSUSE, Arch,
Flatpak, and Snap systems, then retain the command output as release evidence.
