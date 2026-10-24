#!/usr/bin/env python3
"""Exercise actual review/cancel, removal, refresh and history in the VM GUI."""

import importlib.util
import json
from pathlib import Path
import sys
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

assert Path("/run/lam-disposable-acceptance").is_file()
installed = Path("/usr/lib/linux-app-manager")
spec = importlib.util.spec_from_file_location("installed_app", installed / "app.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
application = Adw.Application(application_id="io.github.techmigosglobal.LinuxAppManager.Acceptance")
application.register()
window = module.ManagerWindow(application, str(installed / "lam"))
window.present()
context = GLib.MainContext.default()


def until(condition, timeout=180):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for _ in range(30):
            if not context.pending():
                break
            context.iteration(False)
        if condition():
            return
        time.sleep(0.02)
    raise AssertionError(window.status_label.get_text())


until(lambda: window.apps and window.refresh_button.get_sensitive())
provider = sys.argv[1]
assert next(p for p in window.providers if p["source"] == provider)["healthy"]
assert window.host_mutations_enabled
fixture_name = sys.argv[2]
assert fixture_name in {"hello", "tree"}
fixture = next(app for app in window.apps if app.get("package_name") == fixture_name)
clean = Gtk.CheckButton()


def confirmation():
    return next((w for w in Gtk.Window.get_toplevels()
                 if isinstance(w, Adw.MessageDialog) and w.get_visible()), None)


window.request_uninstall(None, fixture, clean)
until(lambda: confirmation() is not None)
confirmation().response("cancel")
until(lambda: confirmation() is None)
assert not getattr(window, "operation_running", False)
assert any(app["id"] == fixture["id"]
           for app in window.run_cli_json("list", "--all", "--json")["apps"])
assert not any(h["app_id"] == fixture["id"] and h["status"] == "success"
               for h in window.run_cli_json("history", "--json"))
# Re-enter the actual GUI transaction path, including the reviewed preview.
window.request_uninstall(None, fixture, clean)
until(lambda: confirmation() is not None)
confirmation().response("uninstall")
until(lambda: not window.operation_running and window.refresh_button.get_sensitive())
assert not any(app["id"] == fixture["id"] for app in window.apps)
history = window.run_cli_json("history", "--json")
record = next(h for h in history if h["app_id"] == fixture["id"])
assert record["status"] == "success" and record["exit_code"] == 0, record
history_button = Gtk.ToggleButton()
history_button.set_active(True)
window.change_mode(history_button, "history")
assert any(app.get("history_record", {}).get("app_id") == fixture["id"]
           for app in window.visible_apps())
window.get_display().sync()
window.close()
print(json.dumps({"desktop_gui": "passed", "provider": provider,
                  "confirmation_cancel": "passed", "disposable_removal": "passed",
                  "history": "passed", "packages_remaining": len(window.apps)}))
