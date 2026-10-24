#!/usr/bin/env python3
"""Verify normal FUSE runtime CLI/inventory and a mapped GUI window in a VM."""

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

assert Path("/run/lam-disposable-acceptance").is_file()
image = str(Path(sys.argv[1]).resolve())
assert Path("/dev/fuse").is_char_device()
inventory = json.loads(subprocess.check_output([image, "--cli", "list", "--all", "--json"], timeout=90))
assert inventory["apps"]
assert any(app.get("package_name") == "linux-app-manager" for app in inventory["apps"])
with open("/tmp/lam-appimage-normal.log", "w+") as output:
    gui = subprocess.Popen([image], stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            assert gui.poll() is None, "normal AppImage GUI exited before mapping its window"
            windows = subprocess.check_output(["xwininfo", "-root", "-tree"], text=True)
            if '"VIN-LinuxManager"' in windows:
                break
            time.sleep(0.2)
        else:
            raise AssertionError("normal AppImage did not map its application window")
        # Preserve the window tree as evidence of the ordinary GUI entry point.
        print(windows)
        time.sleep(2)
        assert gui.poll() is None, "normal AppImage GUI crashed after mapping"
        print(json.dumps({"normal_appimage_gui": "passed", "packages": len(inventory["apps"]),
                          "launch": "FUSE runtime", "window_title": "VIN-LinuxManager"}))
    finally:
        if gui.poll() is None:
            os.killpg(gui.pid, signal.SIGTERM)
            try:
                gui.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(gui.pid, signal.SIGKILL)
                gui.wait()
        output.seek(0)
        print(output.read())
