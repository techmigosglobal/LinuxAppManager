#!/usr/bin/env python3
"""Deterministic GTK state smoke test; no package operation is invoked."""

import os
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

sys.path.insert(0, ".")
from gui.app import ManagerWindow  # noqa: E402


def main():
    application = Adw.Application(application_id="io.github.linuxappmanager.Lam.Smoke")
    application.register()
    window = ManagerWindow(application, "/bin/true")
    fixture = {
        "apps": [
            {
                "id": "apt:editor",
                "name": "Editor",
                "source": "apt",
                "category": "desktop_application",
                "removable": True,
            },
            {
                "id": "apt:libeditor",
                "name": "libeditor",
                "source": "apt",
                "category": "library",
                "removable": False,
            },
        ],
        "errors": [],
        "providers": [
            {
                "source": "apt",
                "available": True,
                "healthy": True,
                "item_count": 2,
                "message": None,
            },
            {
                "source": "dnf",
                "available": True,
                "healthy": False,
                "item_count": 0,
                "message": "RPM database unavailable",
            },
        ],
        "duplicates": [],
        "history": [
            {
                "id": 1,
                "occurred_at": 1790355600,
                "action": "uninstall",
                "app_id": "apt:old-editor",
                "app_name": "Old Editor",
                "source": "apt",
                "clean": False,
                "status": "success",
                "exit_code": 0,
                "output": None,
            }
        ],
    }
    window.show_inventory(fixture, None)
    assert window.host_mutations_enabled == (
        not bool(os.environ.get("FLATPAK_ID") or os.environ.get("SNAP"))
    )
    assert len(window.visible_apps()) == 1
    assert "Provider warnings" in window.status_label.get_text()
    window.mode = "all"
    assert len(window.visible_apps()) == 2
    window.mode = "history"
    assert len(window.visible_apps()) == 1
    assert window.visible_apps()[0]["history_record"]["status"] == "success"
    assert window.search_entry.get_placeholder_text()
    assert window.refresh_button.get_tooltip_text() == "Refresh installed applications"
    assert window.search_entry.get_accessible_role() == Gtk.AccessibleRole.SEARCH_BOX
    assert window.refresh_button.get_accessible_role() == Gtk.AccessibleRole.BUTTON
    assert window.search_entry.get_focusable()
    assert window.refresh_button.get_focusable()
    for button in window.nav_buttons.values():
        assert button.get_focusable()
    window.close()


if __name__ == "__main__":
    main()
