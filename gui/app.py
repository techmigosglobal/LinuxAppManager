#!/usr/bin/python3
"""GTK frontend for the Linux App Manager Rust CLI."""

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk


CSS = b"""
window { background: @view_bg_color; }
.sidebar { background: alpha(@window_bg_color, .72); padding: 18px 12px; }
.nav-title { font-size: 18px; font-weight: 700; padding: 8px 10px 16px; }
.nav-button { min-height: 42px; }
.page-title { font-size: 24px; font-weight: 700; }
.muted { color: @dim_label_color; }
.app-row { padding: 10px 12px; }
.app-name { font-size: 14px; font-weight: 600; }
.source-pill { color: @accent_color; font-size: 11px; font-weight: 700; }
.details-title { font-size: 22px; font-weight: 700; }
.details { padding: 24px; }
.field-label { color: @dim_label_color; font-size: 12px; }
.field-value { font-size: 14px; }
.empty { padding: 32px; }
"""


def label(text, css=None, wrap=False):
    widget = Gtk.Label(label=text)
    widget.set_xalign(0)
    widget.set_wrap(wrap)
    if css:
        widget.add_css_class(css)
    return widget


class ManagerWindow(Adw.ApplicationWindow):
    def __init__(self, application, lam_binary):
        super().__init__(application=application, title="Linux App Manager")
        self.lam_binary = lam_binary
        self.apps = []
        self.errors = []
        self.history = []
        self.host_mutations_enabled = not bool(
            os.environ.get("FLATPAK_ID") or os.environ.get("SNAP")
        )
        self.duplicate_ids = set()
        self.mode = "applications"
        self.all_packages = False
        self.list_item_widgets = {}
        self.current_visible_apps = []
        self.set_default_size(1160, 760)
        self.set_size_request(760, 520)

        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_title_widget(label("Linux App Manager"))
        self.refresh_button = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        self.refresh_button.set_tooltip_text("Refresh installed applications")
        self.refresh_button.update_property(
            [Gtk.AccessibleProperty.LABEL], ["Refresh installed applications"]
        )
        self.refresh_button.set_focusable(True)
        self.refresh_button.connect("clicked", lambda *_: self.refresh())
        header.pack_end(self.refresh_button)
        toolbar.add_top_bar(header)

        shell = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        shell.append(self.build_sidebar())
        shell.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        shell.append(self.build_main_panel())
        self.nav_buttons["applications"].set_active(True)
        toolbar.set_content(shell)
        self.set_content(toolbar)

        GLib.idle_add(self.refresh)

    def build_sidebar(self):
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        sidebar.set_size_request(205, -1)
        sidebar.add_css_class("sidebar")
        sidebar.append(label("SOFTWARE", "nav-title"))
        self.nav_buttons = {}
        for mode, title, icon in (
            ("applications", "Applications", "view-grid-symbolic"),
            ("duplicates", "Duplicates", "edit-copy-symbolic"),
            ("all", "All packages", "package-x-generic-symbolic"),
            ("history", "History", "document-open-recent-symbolic"),
        ):
            button = Gtk.ToggleButton()
            button.set_child(self.nav_content(title, icon))
            button.update_property([Gtk.AccessibleProperty.LABEL], [title])
            button.set_focusable(True)
            button.add_css_class("nav-button")
            if self.nav_buttons:
                button.set_group(next(iter(self.nav_buttons.values())))
            button.connect("toggled", self.change_mode, mode)
            self.nav_buttons[mode] = button
            sidebar.append(button)
        spacer = Gtk.Box()
        spacer.set_vexpand(True)
        sidebar.append(spacer)
        sidebar.append(label("Scans installed packages and desktop apps from supported sources.", "muted", True))
        return sidebar

    @staticmethod
    def nav_content(title, icon):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        image = Gtk.Image.new_from_icon_name(icon)
        image.set_pixel_size(18)
        box.append(image)
        box.append(label(title))
        return box

    def build_main_panel(self):
        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        main.set_hexpand(True)

        top = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        top.set_margin_top(22)
        top.set_margin_start(24)
        top.set_margin_end(24)
        top.set_margin_bottom(16)
        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.page_title = label("Applications", "page-title")
        title_row.append(self.page_title)
        self.count_label = label("", "muted")
        title_row.append(self.count_label)
        top.append(title_row)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search by app, package, publisher, or source")
        self.search_entry.update_property(
            [Gtk.AccessibleProperty.LABEL], ["Search installed software"]
        )
        self.search_entry.set_focusable(True)
        self.search_entry.connect("search-changed", lambda *_: self.render_rows())
        top.append(self.search_entry)
        self.status_label = label("", "muted", True)
        self.status_label.set_visible(False)
        top.append(self.status_label)
        main.append(top)

        split = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        split.set_wide_handle(True)
        split.set_vexpand(True)
        split.set_position(470)

        self.app_store = Gtk.StringList.new([])
        self.selection = Gtk.SingleSelection.new(self.app_store)
        self.selection.set_autoselect(False)
        self.selection.set_can_unselect(True)
        self.selection.connect("notify::selected", self.select_list_item)
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self.setup_list_item)
        factory.connect("bind", self.bind_list_item)
        self.list_view = Gtk.ListView.new(self.selection, factory)
        self.list_view.set_focusable(True)
        self.list_view.add_css_class("boxed-list")
        list_scroll = Gtk.ScrolledWindow()
        list_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        list_scroll.set_child(self.list_view)
        list_scroll.set_min_content_width(330)
        self.list_stack = Gtk.Stack()
        self.list_stack.add_named(list_scroll, "list")
        self.list_stack.add_named(label("No matching software found.", "empty", True), "empty")
        split.set_start_child(self.list_stack)

        self.details = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        self.details.add_css_class("details")
        self.details.set_size_request(330, -1)
        details_scroll = Gtk.ScrolledWindow()
        details_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        details_scroll.set_child(self.details)
        split.set_end_child(details_scroll)
        main.append(split)
        return main

    def change_mode(self, button, mode):
        if not button.get_active():
            return
        self.mode = mode
        self.all_packages = mode == "all"
        titles = {
            "applications": "Applications",
            "duplicates": "Duplicate installations",
            "all": "All packages",
            "history": "Operation history",
        }
        self.page_title.set_text(titles[mode])
        self.render_rows()

    def refresh(self):
        if not self.refresh_button.get_sensitive():
            return GLib.SOURCE_REMOVE
        self.refresh_button.set_sensitive(False)
        self.status_label.set_text("Scanning installed applications…")
        self.status_label.set_visible(True)
        threading.Thread(target=self.load_inventory, daemon=True).start()
        return GLib.SOURCE_REMOVE

    def run_cli_json(self, *args):
        result = subprocess.run(
            [self.lam_binary, *args], capture_output=True, text=True, timeout=300, check=False
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or f"lam exited with status {result.returncode}")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"Could not read the scan result: {error}") from error

    def load_inventory(self):
        try:
            inventory = self.run_cli_json("list", "--all", "--json")
            try:
                history = self.run_cli_json("history", "--json")
            except Exception:
                history = []
            GLib.idle_add(self.show_inventory, inventory, None, history)
        except Exception as error:
            GLib.idle_add(self.show_inventory, None, str(error))

    def show_inventory(self, inventory, error, history=None):
        self.refresh_button.set_sensitive(True)
        if error:
            self.status_label.set_text(f"Scan failed: {error}")
            self.status_label.set_visible(True)
            return GLib.SOURCE_REMOVE
        self.apps = inventory.get("apps", [])
        self.errors = inventory.get("errors", [])
        self.history = inventory.get("history", []) if history is None else history
        self.providers = inventory.get("providers", [])
        self.duplicate_ids = {
            app["id"] for group in inventory.get("duplicates", []) for app in group
        }
        healthy_sources = ", ".join(
            sorted((p.get("source") or "unknown").upper() for p in self.providers if p.get("healthy"))
        ) or "no healthy sources"
        unhealthy_sources = [
            f"{(p.get('source') or 'unknown').upper()}: {p.get('message') or 'unavailable'}"
            for p in self.providers
            if not p.get("healthy")
        ]
        desktop_apps = sum(app.get("category") == "desktop_application" for app in self.apps)
        summary = f"Scan complete: {len(self.apps):,} package entries from {healthy_sources}; {desktop_apps:,} desktop applications. CLI tools and system components are in All packages."
        if unhealthy_sources:
            summary += " Provider warnings: " + " · ".join(unhealthy_sources)
        if self.errors:
            summary += " Source warnings: " + " · ".join(self.errors)
        self.status_label.set_text(summary)
        self.status_label.set_visible(True)
        self.render_rows()
        return GLib.SOURCE_REMOVE

    def visible_apps(self):
        if self.mode == "history":
            rows = []
            for record in self.history:
                rows.append(
                    {
                        "id": f"history:{record.get('id', '')}",
                        "name": record.get("app_name") or "Unknown application",
                        "source": record.get("source") or "unknown",
                        "version": record.get("status") or "unknown",
                        "category": "history",
                        "history_record": record,
                        "removable": False,
                    }
                )
            query = self.search_entry.get_text().strip().casefold()
            if query:
                rows = [
                    row
                    for row in rows
                    if query in " ".join(str(value or "") for value in row.values()).casefold()
                ]
            return rows
        apps = self.apps
        if self.mode == "applications":
            apps = [a for a in apps if a["category"] == "desktop_application"]
        elif self.mode == "duplicates":
            apps = [a for a in apps if a["id"] in self.duplicate_ids]
        query = self.search_entry.get_text().strip().casefold()
        if query:
            apps = [a for a in apps if query in " ".join(str(a.get(k) or "") for k in (
                "name", "package_name", "publisher", "source", "version", "description"
            )).casefold()]
        return apps

    def render_rows(self):
        apps = self.visible_apps()
        self.current_visible_apps = apps
        self.count_label.set_text(f"{len(apps):,}")
        if not apps:
            self.app_store = Gtk.StringList.new([])
            self.selection.set_model(self.app_store)
            self.selection.set_selected(Gtk.INVALID_LIST_POSITION)
            self.list_stack.set_visible_child_name("empty")
            self.show_details(None)
            return
        self.app_store = Gtk.StringList.new([str(i) for i in range(len(apps))])
        self.selection.set_model(self.app_store)
        self.selection.set_selected(0)
        self.list_stack.set_visible_child_name("list")

    def setup_list_item(self, _factory, list_item):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row.add_css_class("app-row")
        icon = Gtk.Image.new_from_icon_name("application-x-executable-symbolic")
        row.append(icon)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        name = label("", "app-name")
        name.set_ellipsize(3)
        body.append(name)
        info = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        body.append(info)
        row.append(body)
        list_item.set_child(row)
        self.list_item_widgets[list_item] = {"icon": icon, "name": name, "info": info}

    def bind_list_item(self, _factory, list_item):
        position = list_item.get_position()
        if position >= len(self.current_visible_apps):
            return
        app = self.current_visible_apps[position]
        widgets = self.list_item_widgets[list_item]
        widgets["name"].set_text(app.get("name") or app.get("package_name") or "Unknown application")
        self.set_app_icon(widgets["icon"], app, 32)
        info = widgets["info"]
        child = info.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            info.remove(child)
            child = next_child
        info.append(label((app.get("source") or "unknown").replace("_", " ").upper(), "source-pill"))
        installation = app.get("installation")
        if installation and installation != "unknown":
            info.append(label(installation.upper(), "muted"))
        if app.get("version"):
            version = label(app["version"], "muted")
            version.set_ellipsize(3)
            info.append(version)
        if app.get("architecture"):
            info.append(label(app["architecture"], "muted"))

    def select_list_item(self, _selection, _property):
        position = self.selection.get_selected()
        app = self.current_visible_apps[position] if position < len(self.current_visible_apps) else None
        if app and app.get("history_record"):
            self.show_history_details(app)
        else:
            self.show_details(app)

    def clear_details(self):
        child = self.details.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.details.remove(child)
            child = next_child

    def add_field(self, title, value):
        if not value:
            return
        block = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        block.append(label(title, "field-label"))
        block.append(label(str(value), "field-value", True))
        self.details.append(block)

    def show_history_details(self, app):
        self.clear_details()
        record = app["history_record"]
        self.details.append(label(app.get("name") or "Operation", "details-title", True))
        self.add_field("ACTION", record.get("action"))
        self.add_field("SOURCE", (record.get("source") or "unknown").upper())
        self.add_field("STATUS", record.get("status"))
        self.add_field("EXIT CODE", record.get("exit_code"))
        occurred_at = record.get("occurred_at")
        if occurred_at:
            self.add_field(
                "TIME",
                datetime.fromtimestamp(occurred_at).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
            )
        if record.get("clean"):
            self.add_field("MODE", "Clean / provider data removal requested")
        if record.get("output"):
            self.add_field("OUTPUT", record["output"])
        self.details.append(label("History is informational; no package operation is started from this view.", "muted", True))

    def show_details(self, app):
        self.clear_details()
        if not app:
            self.details.append(label("Select an application to see its details.", "muted empty", True))
            return
        identity = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        app_icon = Gtk.Image.new_from_icon_name("application-x-executable-symbolic")
        self.set_app_icon(app_icon, app, 56)
        identity.append(app_icon)
        identity.append(label(app.get("name") or "Unknown application", "details-title", True))
        self.details.append(identity)
        description = app.get("description")
        if description:
            self.details.append(label(description, "muted", True))
        self.add_field("SOURCE", (app.get("source") or "unknown").upper())
        self.add_field("INSTALLATION", app.get("installation"))
        self.add_field("VERSION", app.get("version"))
        self.add_field("PACKAGE", app.get("package_name"))
        self.add_field("CATEGORY", (app.get("category") or "unknown").replace("_", " ").title())
        self.add_field("PUBLISHER", app.get("publisher"))
        self.add_field("ARCHITECTURE", app.get("architecture"))
        self.add_field("EXECUTABLE", app.get("executable"))
        size = app.get("installed_size")
        if size:
            self.add_field("INSTALLED SIZE", self.human_size(size))
        self.add_field("DESKTOP ENTRY", app.get("desktop_file"))
        if app.get("system_protected"):
            self.add_field("SAFETY", "Protected system package")
        elif not app.get("removable", True):
            self.add_field("SAFETY", "Removal is disabled for this package")

        spacer = Gtk.Box()
        spacer.set_vexpand(True)
        self.details.append(spacer)
        self.details.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        self.details.append(label("Review the package command and affected packages before making changes.", "muted", True))
        clean = Gtk.CheckButton(label="Include app data in plan when supported")
        self.details.append(clean)
        plan_button = Gtk.Button(label="Review removal plan")
        plan_button.set_halign(Gtk.Align.START)
        plan_button.connect("clicked", self.review_plan, app, clean)
        self.details.append(plan_button)
        uninstall_button = Gtk.Button(label="Uninstall…")
        uninstall_button.add_css_class("destructive-action")
        uninstall_button.set_halign(Gtk.Align.START)
        uninstall_button.set_sensitive(bool(app.get("removable", True)) and not app.get("system_protected", False))
        uninstall_button.connect("clicked", self.request_uninstall, app, clean)
        self.details.append(uninstall_button)
        if not self.host_mutations_enabled:
            plan_button.set_sensitive(False)
            uninstall_button.set_sensitive(False)
            self.details.append(
                label(
                    "Host package changes are disabled in sandboxed builds. Install the native package for reviewed removal operations.",
                    "muted",
                    True,
                )
            )
        if app.get("system_protected"):
            self.details.append(label("This is a protected system package and cannot be removed here.", "muted", True))
        elif not app.get("removable", True):
            self.details.append(label("This package is listed for visibility, but the app will not remove it automatically.", "muted", True))

    def set_app_icon(self, image, app, pixel_size):
        icon = (app.get("icon") or "").strip()
        if icon and Path(icon).is_file():
            image.set_from_file(icon)
        elif icon and Gtk.IconTheme.get_for_display(self.get_display()).has_icon(icon):
            image.set_from_icon_name(icon)
        else:
            image.set_from_icon_name("application-x-executable-symbolic")
        image.set_pixel_size(pixel_size)

    def review_plan(self, _button, app, clean):
        self.status_label.set_text("Calculating the package removal transaction…")
        self.status_label.set_visible(True)
        args = ["plan-remove", app["id"], "--json"]
        if clean.get_active():
            args.append("--clean")

        def worker():
            try:
                result = self.run_cli_json(*args)
                GLib.idle_add(self.show_plan, result, None)
            except Exception as error:
                GLib.idle_add(self.show_plan, None, str(error))

        threading.Thread(target=worker, daemon=True).start()

    def show_plan(self, result, error):
        self.status_label.set_visible(False)
        if error or not result or not result.get("ok"):
            message = error or (result or {}).get("error", "Could not build a removal plan.")
            dialog = Adw.MessageDialog.new(self, "Removal plan unavailable", message)
            dialog.add_response("close", "Close")
            dialog.present()
            return GLib.SOURCE_REMOVE
        command = " ".join(result.get("argv", []))
        lines = [f"Command: {command}", "", "No changes have been made."]
        preview = result.get("preview", [])
        if preview:
            lines.extend(["", "Packages in the removal transaction:", *[f"• {item}" for item in preview]])
        if result.get("requires_elevation"):
            lines.extend(["", "This operation uses the system authorization dialog."])
        dialog = Adw.MessageDialog.new(self, "Removal plan", "Review this plan before continuing.")
        dialog.set_body("\n".join(lines))
        dialog.add_response("close", "Close")
        dialog.set_default_response("close")
        dialog.present()
        return GLib.SOURCE_REMOVE

    def request_uninstall(self, _button, app, clean):
        self.status_label.set_text("Calculating the package transaction. A system authorization prompt may appear.")
        self.status_label.set_visible(True)
        clean_mode = clean.get_active()
        args = ["plan-remove", app["id"], "--json"]
        if clean_mode:
            args.append("--clean")

        def worker():
            try:
                plan = self.run_cli_json(*args)
                GLib.idle_add(self.confirm_uninstall, app, clean_mode, plan, None)
            except Exception as error:
                GLib.idle_add(self.confirm_uninstall, app, clean_mode, None, str(error))

        threading.Thread(target=worker, daemon=True).start()

    def confirm_uninstall(self, app, clean, plan, error):
        self.status_label.set_visible(False)
        if error or not plan or not plan.get("ok"):
            message = error or (plan or {}).get("error", "Could not build a removal plan.")
            dialog = Adw.MessageDialog.new(self, "Uninstall unavailable", message)
            dialog.add_response("close", "Close")
            dialog.present()
            return GLib.SOURCE_REMOVE

        command = list(plan.get("argv", []))
        if plan.get("requires_elevation"):
            executable = {
                "apt": "/usr/bin/apt-get",
                "dnf": "/usr/bin/dnf",
                "pacman": "/usr/bin/pacman",
            }.get(app.get("source"))
            command = ["pkexec", executable or command[0], *command[1:]]
        lines = [f"Command: {' '.join(command)}", ""]
        affected = plan.get("preview", [])
        if affected:
            lines.extend(["The package manager plans to remove:", *[f"• {item}" for item in affected], ""])
        else:
            lines.append("The provider did not return a dependency list; its package manager will resolve the transaction.")
        if clean:
            lines.extend(["", "Clean mode will also remove package configuration or application data where supported."])
        lines.extend(["", "Choose Uninstall to start the transaction. Progress and command output will stay visible."])

        dialog = Adw.MessageDialog.new(self, f"Uninstall {app.get('name', 'package')}?", "Review the transaction before continuing.")
        dialog.set_body("\n".join(lines))
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("uninstall", "Uninstall")
        dialog.set_response_appearance("uninstall", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self.on_uninstall_confirmation, app, clean, affected)
        dialog.present()
        return GLib.SOURCE_REMOVE

    def on_uninstall_confirmation(self, _dialog, response, app, clean, expected_preview):
        if response == "uninstall":
            self.start_uninstall(app, clean, expected_preview)

    def start_uninstall(self, app, clean, expected_preview):
        window = Adw.Window()
        window.set_transient_for(self)
        window.set_modal(True)
        window.set_title(f"Uninstalling {app.get('name', 'package')}")
        window.set_default_size(700, 460)
        window.connect("close-request", self.prevent_closing_running_transaction)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_top(20)
        content.set_margin_bottom(16)
        content.set_margin_start(20)
        content.set_margin_end(20)
        title = label(f"Uninstalling {app.get('name', 'package')}", "page-title")
        content.append(title)
        self.operation_status = label("Starting package manager…", "muted", True)
        content.append(self.operation_status)
        self.operation_progress = Gtk.ProgressBar()
        self.operation_progress.set_show_text(True)
        self.operation_progress.set_text("Working")
        content.append(self.operation_progress)

        self.operation_log = Gtk.TextView()
        self.operation_log.set_editable(False)
        self.operation_log.set_cursor_visible(False)
        self.operation_log.set_monospace(True)
        self.operation_log.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.operation_log_buffer = self.operation_log.get_buffer()
        log_scroll = Gtk.ScrolledWindow()
        log_scroll.set_vexpand(True)
        log_scroll.set_child(self.operation_log)
        content.append(log_scroll)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        footer.append(label("Authorization may be requested by your desktop session.", "muted", True))
        self.operation_close = Gtk.Button(label="Close")
        self.operation_close.set_sensitive(False)
        self.operation_close.set_halign(Gtk.Align.END)
        self.operation_close.connect("clicked", lambda *_: window.close())
        footer.append(self.operation_close)
        content.append(footer)
        window.set_content(content)
        self.operation_window = window
        self.operation_running = True
        window.present()
        GLib.timeout_add(100, self.pulse_operation_progress)

        args = [self.lam_binary, "uninstall", app["id"], "--yes"]
        if clean:
            args.append("--clean")
        args.extend(["--expected-preview", ",".join(expected_preview)])

        def worker():
            try:
                process = subprocess.Popen(
                    args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1,
                )
                self.operation_process = process
                for line in process.stdout:
                    GLib.idle_add(self.append_operation_output, line.rstrip("\n"))
                code = process.wait()
                GLib.idle_add(self.finish_uninstall, app, code, None)
            except Exception as error:
                GLib.idle_add(self.finish_uninstall, app, 1, str(error))

        threading.Thread(target=worker, daemon=True).start()

    def prevent_closing_running_transaction(self, _window):
        return bool(getattr(self, "operation_running", False))

    def pulse_operation_progress(self):
        if not getattr(self, "operation_running", False):
            return GLib.SOURCE_REMOVE
        self.operation_progress.pulse()
        return GLib.SOURCE_CONTINUE

    def append_operation_output(self, line):
        end = self.operation_log_buffer.get_end_iter()
        self.operation_log_buffer.insert(end, line + "\n")
        end = self.operation_log_buffer.get_end_iter()
        mark = self.operation_log_buffer.create_mark(None, end, False)
        self.operation_log.scroll_to_mark(mark, 0.0, False, 0.0, 1.0)
        return GLib.SOURCE_REMOVE

    def finish_uninstall(self, app, code, error):
        self.operation_running = False
        self.operation_progress.set_fraction(1.0 if code == 0 else 0.0)
        if error:
            self.operation_status.set_text(f"Could not start uninstall: {error}")
            self.append_operation_output(error)
        elif code == 0:
            self.operation_status.set_text("Uninstall completed successfully.")
            self.append_operation_output("Uninstall completed successfully.")
        else:
            self.operation_status.set_text(f"Uninstall failed (exit status {code}).")
            self.append_operation_output(f"Uninstall failed (exit status {code}).")
        self.operation_close.set_sensitive(True)
        self.refresh()
        return GLib.SOURCE_REMOVE

    @staticmethod
    def human_size(size):
        amount = float(size)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if amount < 1000 or unit == "TB":
                return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
            amount /= 1000


def main():
    parser = argparse.ArgumentParser(description="Linux App Manager GUI")
    parser.add_argument("--lam-bin", required=True, help="path to the Rust lam executable")
    args = parser.parse_args()
    application = Adw.Application(
        application_id="io.github.linuxappmanager.Lam",
        flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
    )
    application.connect("activate", lambda app: ManagerWindow(app, args.lam_bin).present())
    return application.run([])


if __name__ == "__main__":
    sys.exit(main())
