#!/usr/bin/env python3
"""Test the real GUI subprocess policy without requiring GTK or a display."""

import ast
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_environment_policy():
    tree = ast.parse((ROOT / "gui/app.py").read_text())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == "host_cli_environment")
    namespace = {"os": os}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "gui/app.py", "exec"), namespace)
    return namespace["host_cli_environment"]


class AppImageEnvironmentTests(unittest.TestCase):
    def test_real_host_child_uses_host_paths_and_keeps_session(self):
        environment = {
            "LAM_APPIMAGE": "1", "LAM_APPIMAGE_HOST_PATH": "/usr/bin:/bin",
            "PATH": "/bundle/usr/bin", "LD_LIBRARY_PATH": "/bundle/usr/lib",
            "PYTHONHOME": "/bundle/usr", "PYTHONPATH": "/bundle/python",
            "GI_TYPELIB_PATH": "/bundle/typelibs", "GIO_MODULE_DIR": "/bundle/gio",
            "GSETTINGS_SCHEMA_DIR": "/bundle/schemas", "XDG_DATA_DIRS": "/bundle/share",
            "GDK_PIXBUF_MODULE_FILE": "/bundle/loaders.cache", "GTK_PATH": "/bundle/gtk",
            "DISPLAY": ":93", "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
            "XDG_RUNTIME_DIR": "/run/user/1000", "HOME": "/home/example",
            "SNAP": "/snap/example", "FLATPAK_ID": "example.sandbox",
        }
        with patch.dict(os.environ, environment, clear=True):
            clean = load_environment_policy()()
        result = subprocess.run(["/usr/bin/env"], env=clean, text=True, capture_output=True, check=True)
        self.assertNotIn("/bundle", result.stdout)
        for key in ("DISPLAY", "DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR", "HOME", "SNAP", "FLATPAK_ID"):
            self.assertEqual(clean[key], environment[key])
        self.assertEqual(clean["PATH"], "/usr/bin:/bin")
        self.assertEqual(clean["LAM_APPIMAGE"], "1")

    def test_native_environment_is_preserved(self):
        environment = {"PATH": "/usr/bin", "PYTHONPATH": "/native/custom", "LD_LIBRARY_PATH": "/native/lib"}
        with patch.dict(os.environ, environment, clear=True):
            self.assertEqual(load_environment_policy()(), environment)


if __name__ == "__main__":
    unittest.main()
