#!/usr/bin/env python3
"""Keyboard/focus and accessible-name smoke checks for the critical GTK surface."""

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

sys.path.insert(0, ".")
from gui.app import ManagerWindow  # noqa: E402


def main():
    application = Adw.Application(application_id="io.github.linuxappmanager.Lam.AccessibilitySmoke")
    application.register()
    window = ManagerWindow(application, "/bin/true")

    assert window.search_entry.get_accessible_role() == Gtk.AccessibleRole.SEARCH_BOX
    assert window.refresh_button.get_accessible_role() == Gtk.AccessibleRole.BUTTON
    assert window.search_entry.get_focusable()
    assert window.refresh_button.get_focusable()
    assert window.search_entry.get_placeholder_text()
    assert window.refresh_button.get_tooltip_text()

    for mode, button in window.nav_buttons.items():
        assert button.get_focusable(), mode
        assert button.get_accessible_role() == Gtk.AccessibleRole.TOGGLE_BUTTON
        assert button.get_child() is not None

    fixture = {
        "apps": [{
            "id": "apt:editor",
            "name": "Editor",
            "source": "apt",
            "category": "desktop_application",
            "removable": True,
        }],
        "errors": [],
        "providers": [],
        "duplicates": [],
        "history": [],
    }
    window.show_inventory(fixture, None)
    assert window.selection.get_selected() == 0
    assert window.list_view.get_focusable()
    window.close()


if __name__ == "__main__":
    main()
