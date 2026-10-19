#!/usr/bin/env python3
"""Exercise the installed GUI and its real CLI in a disposable desktop session."""

import importlib.util
import json
from pathlib import Path
import sys

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
inventory = window.run_cli_json("list", "--all", "--json")
history = window.run_cli_json("history", "--json")
expected = sys.argv[1]
providers = {p["source"]: p for p in inventory["providers"]}
assert providers[expected]["healthy"], providers
assert inventory["apps"], "installed package database unexpectedly empty"
assert any(app.get("package_name", "").startswith("linux-app-manager") for app in inventory["apps"])
window.show_inventory(inventory, None, history)
window.present()
context = GLib.MainContext.default()
for _ in range(30):
    if context.pending():
        context.iteration(False)
window.get_display().sync()
assert window.get_title() == "VIN-LinuxManager"
assert window.host_mutations_enabled
assert window.refresh_button.get_sensitive()
window.close()
print(json.dumps({"installed_gui": "passed", "provider": expected,
                  "packages": len(inventory["apps"]), "history_entries": len(history)}))
