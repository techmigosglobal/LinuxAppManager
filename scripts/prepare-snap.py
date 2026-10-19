#!/usr/bin/env python3
"""Create Snap metadata around the already verified portable application runtime."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]


def prepare(appdir, report, commit):
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("a full source commit is required")
    expected = json.loads(report.read_text())
    actual = json.loads((appdir / "usr/share/linux-app-manager/AppImage.build.json").read_text())
    if actual != expected or actual.get("development_builder") is not False:
        raise ValueError("only an unchanged production runtime can be packaged")
    manifest = yaml.safe_load((ROOT / "snap/snapcraft.yaml").read_text())
    if actual.get("version") != manifest["version"]:
        raise ValueError("portable runtime and Snap versions differ")
    if manifest["confinement"] != "classic" or manifest["grade"] != "devel":
        raise ValueError("Snap remains classic/devel until review and installed-Snap acceptance")
    if not (appdir / "AppRun").is_file() or not (appdir / "usr/bin/lam").is_file():
        raise ValueError("portable runtime lacks application entry points")
    # Classic snaps must load their declared base's glibc, even on older hosts.
    # Preserve bundled GTK/Python libraries while avoiding host-absolute /usr.
    patched = 0
    for path in sorted(appdir.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        with path.open("rb") as stream:
            header = stream.read(20)
        if header[:4] != b"\x7fELF" or len(header) < 20:
            continue
        byteorder = "little" if header[5] == 1 else "big"
        if int.from_bytes(header[16:18], byteorder) not in (2, 3):
            # Python ships build-configuration .o files; these have no loader
            # or dynamic section and must not be passed to patchelf.
            continue
        relative = os.path.relpath(appdir / "usr/lib", path.parent)
        rpath = f"$ORIGIN/{relative}:/snap/core24/current/lib/x86_64-linux-gnu:/snap/core24/current/usr/lib/x86_64-linux-gnu"
        interpreter = subprocess.run(["patchelf", "--print-interpreter", str(path)], capture_output=True, text=True)
        if interpreter.returncode == 0:
            subprocess.run(["patchelf", "--set-interpreter", "/snap/core24/current/lib64/ld-linux-x86-64.so.2", str(path)], check=True)
        subprocess.run(["patchelf", "--force-rpath", "--set-rpath", rpath, str(path)], check=True)
        patched += 1
    metadata = {key: manifest[key] for key in ("name", "version", "summary", "description", "base", "grade", "confinement")}
    metadata["architectures"] = ["amd64"]
    metadata["apps"] = {manifest["name"]: {"command": "AppRun"}}
    meta = appdir / "meta"
    (meta / "gui").mkdir(parents=True, exist_ok=True)
    (meta / "snap.yaml").write_text(yaml.safe_dump(metadata, sort_keys=False))
    desktop_name = "io.github.techmigosglobal.LinuxAppManager.desktop"
    desktop = (appdir / desktop_name).read_text()
    desktop = re.sub(r"^Exec=.*$", f"Exec={manifest['name']}", desktop, flags=re.M)
    desktop = re.sub(r"^Icon=.*$", "Icon=${SNAP}/meta/gui/icon.png", desktop, flags=re.M)
    (meta / "gui" / desktop_name).write_text(desktop)
    shutil.copyfile(appdir / "io.github.techmigosglobal.LinuxAppManager.png", meta / "gui/icon.png")
    (appdir / "usr/share/linux-app-manager/Snap.build.json").write_text(json.dumps({
        "version": manifest["version"], "source_commit": commit,
        "confinement": "classic", "grade": "devel", "host_mutations": False,
        "base": "core24", "base_linked_elf_files": patched,
        "runtime": actual,
    }, indent=2) + "\n")
    return manifest["name"], manifest["version"]


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit("usage: prepare-snap.py APPDIR RUNTIME_REPORT SOURCE_COMMIT")
    name, version = prepare(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3])
    print(f"{name}_{version}_amd64.snap")
