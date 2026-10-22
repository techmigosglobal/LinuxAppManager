#!/usr/bin/env python3
"""Exercise the installed GUI and its real CLI in a disposable desktop session."""

import importlib.util
import json
from pathlib import Path
import sys
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib

installed = Path("/usr/lib/linux-app-manager")
spec = importlib.util.spec_from_file_location("installed_app", installed / "app.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
application = Adw.Application(application_id="io.github.techmigosglobal.LinuxAppManager.InstalledSmoke")
application.register()
window = module.ManagerWindow(application, str(installed / "lam"))
window.present()
# Exercise the real idle-triggered startup scan and its completion callback.
# Manually injecting inventory races the queued refresh and leaves the button
# temporarily disabled even though the application is behaving correctly.
context = GLib.MainContext.default()
deadline = time.monotonic() + 90
while time.monotonic() < deadline:
    for _ in range(20):
        if not context.pending():
            break
        context.iteration(False)
    if window.apps and window.refresh_button.get_sensitive():
        break
    time.sleep(0.02)
assert window.apps, window.status_label.get_text()
inventory = {"apps": window.apps, "providers": window.providers}
history = window.history
expected = sys.argv[1]
providers = {p["source"]: p for p in inventory["providers"]}
assert providers[expected]["healthy"], providers
assert inventory["apps"], "installed package database unexpectedly empty"
assert any(app.get("package_name", "").startswith("linux-app-manager") for app in inventory["apps"])
window.get_display().sync()
assert window.get_title() == "VIN-LinuxManager"
assert window.host_mutations_enabled
assert window.refresh_button.get_sensitive()
window.close()
print(json.dumps({"installed_gui": "passed", "provider": expected,
                  "packages": len(inventory["apps"]), "history_entries": len(history)}))
