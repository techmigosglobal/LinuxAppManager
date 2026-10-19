"""Relocatable entry point. Only GUI processes inherit the bundled runtime."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def host_environment():
    from app import host_cli_environment

    return host_cli_environment()


def main():
    root = Path(os.environ["LAM_APPIMAGE_DIRECTORY"])
    lam = root / "usr/bin/lam"
    if sys.argv[1:2] == ["--cli"]:
        os.execve(lam, [str(lam), *sys.argv[2:]], host_environment())
    with tempfile.TemporaryDirectory(prefix="vin-linuxmanager-pixbuf-") as temporary:
        query = root / "usr/bin/gdk-pixbuf-query-loaders"
        loaders = sorted((root / "usr/lib/gdk-pixbuf-loaders").glob("*.so"))
        if loaders:
            cache = Path(temporary) / "loaders.cache"
            output = subprocess.check_output([str(query), *(str(path) for path in loaders)])
            cache.write_bytes(output)
            os.environ["GDK_PIXBUF_MODULE_FILE"] = str(cache)
            os.environ["GDK_PIXBUF_MODULEDIR"] = str(root / "usr/lib/gdk-pixbuf-loaders")
        # GTK may initialize pixbuf while its typelib is imported. Configure
        # loaders first, so a newer host SVG loader cannot enter this runtime.
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw
        import app
        if sys.argv[1:] == ["--appimage-smoke-test"]:
            application = Adw.Application(application_id="io.github.techmigosglobal.LinuxAppManager.Smoke")
            application.register()
            window = app.ManagerWindow(application, str(lam))
            inventory = window.run_cli_json("list", "--all", "--json")
            window.show_inventory(inventory, None, [])
            window.present()
            window.get_display().sync()
            assert window.get_title() == "VIN-LinuxManager"
            assert any(provider["source"] == "app_image" for provider in inventory["providers"])
            print(json.dumps({"gui_smoke": "passed", "packages": len(inventory["apps"]),
                              "python": sys.version.split()[0]}))
            window.close()
            return 0
        sys.argv = [str(root / "usr/lib/linux-app-manager/app.py"), "--lam-bin", str(lam), *sys.argv[1:]]
        return app.main()


if __name__ == "__main__":
    sys.exit(main())
