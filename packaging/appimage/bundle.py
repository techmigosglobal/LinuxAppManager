#!/usr/bin/python3
"""Build an AppDir from the Ubuntu 24.04 runtime; fail on missing dependencies."""

import glob
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import sysconfig
import tomllib

def parse_dpkg_owners(output):
    """Read ownership records without treating dpkg diversion prose as names."""
    identifier = r"[a-z0-9][a-z0-9+.-]*(?::[a-z0-9][a-z0-9-]*)?"
    packages = set()
    for line in output.splitlines():
        owners, separator, _path = line.partition(": /")
        if not separator:
            continue
        diversion = re.fullmatch(rf"diversion by ({identifier}) (?:from|to)", owners)
        if diversion:
            # Include the real diverting package's license as well as any ordinary
            # ownership records. Local/admin diversions identify no package.
            packages.add(diversion.group(1))
            continue
        for owner in owners.split(","):
            owner = owner.strip()
            if re.fullmatch(identifier, owner):
                packages.add(owner)
    return packages


source, appdir, binary = map(lambda path: Path(path).resolve(), sys.argv[1:])
copied = set()


def copy_file(path, destination):
    path = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path.resolve(), destination)
    copied.add(str(path))
    copied.add(str(path.resolve()))


def copy_tree(path, destination):
    path = Path(path)
    if not path.is_dir():
        raise RuntimeError(f"required runtime directory missing: {path}")
    shutil.copytree(path, destination, symlinks=False, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "test", "tests", "ensurepip"))
    copied.update(str(item) for item in path.rglob("*") if item.is_file())


copy_file(binary, appdir / "usr/bin/lam")
copy_file(Path(sys.executable), appdir / "usr/bin/python3")
python_lib = Path(sysconfig.get_path("stdlib"))
copy_tree(python_lib, appdir / "usr/lib" / python_lib.name)
for module in ("gi", "cairo"):
    copy_tree(Path("/usr/lib/python3/dist-packages") / module,
              appdir / "usr/lib/python3/dist-packages" / module)
for directory in ("icons/Adwaita",):
    copy_tree(Path("/usr/share") / directory, appdir / "usr/share" / directory)
schema_dir = appdir / "usr/share/glib-2.0/schemas"
for pattern in ("org.gtk.*", "org.gnome.desktop.*"):
    for schema in Path("/usr/share/glib-2.0/schemas").glob(pattern):
        if schema.is_file():
            copy_file(schema, schema_dir / schema.name)
subprocess.run(["glib-compile-schemas", str(schema_dir)], check=True)
mime_dir = appdir / "usr/share/mime"
copy_file("/usr/share/mime/packages/freedesktop.org.xml", mime_dir / "packages/freedesktop.org.xml")
subprocess.run(["update-mime-database", str(mime_dir)], check=True)
copy_file("/usr/share/icons/hicolor/index.theme", appdir / "usr/share/icons/hicolor/index.theme")
copy_tree("/usr/lib/x86_64-linux-gnu/girepository-1.0", appdir / "usr/lib/girepository-1.0")
for module in ("/usr/lib/x86_64-linux-gnu/gio/modules",):
    copy_tree(module, appdir / "usr/lib/gio/modules")
for loader in glob.glob("/usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/*/loaders/*.so"):
    copy_file(loader, appdir / "usr/lib/gdk-pixbuf-loaders" / Path(loader).name)
query = "/usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/gdk-pixbuf-query-loaders"
copy_file(query, appdir / "usr/bin/gdk-pixbuf-query-loaders")

# GTK's typelibs load these libraries at runtime, outside ELF DT_NEEDED.
seeds = ["libgtk-4.so.1", "libadwaita-1.so.0", "libgirepository-1.0.so.1",
         "libgdk_pixbuf-2.0.so.0", "libcairo-gobject.so.2", "libpangocairo-1.0.so.0"]
search = subprocess.check_output(["/sbin/ldconfig", "-p"], text=True)
resolved = {}
for line in search.splitlines():
    match = re.match(r"\s*(\S+) .* => (\S+)$", line)
    if match:
        resolved.setdefault(match[1], match[2])
for library in seeds:
    if library not in resolved:
        raise RuntimeError(f"required runtime library missing: {library}")
    copy_file(resolved[library], appdir / "usr/lib" / library)

# glibc and GPU drivers belong to the host. Build on the oldest supported glibc.
excluded = re.compile(r"^(ld-linux|lib(c|m|pthread|dl|rt|resolv|util|anl)\.so|"
                      r"libnss_|lib(EGL|GLX|GLdispatch|GL|OpenGL|vulkan|drm|gbm)\.)")
queue = [path for path in appdir.rglob("*") if path.is_file() and path.open("rb").read(4) == b"\x7fELF"]
seen = set()
while queue:
    path = queue.pop()
    if path in seen:
        continue
    seen.add(path)
    result = subprocess.run(["ldd", str(path)], text=True, capture_output=True)
    if "not found" in result.stdout:
        raise RuntimeError(f"unresolved dependency for {path}: {result.stdout}")
    for line in result.stdout.splitlines():
        match = re.match(r"\s*(\S+) => (/\S+) ", line)
        if not match or excluded.match(match[1]):
            continue
        soname, dependency = match.groups()
        destination = appdir / "usr/lib" / soname
        if not destination.exists():
            copy_file(dependency, destination)
            queue.append(destination)

app_id = "io.github.techmigosglobal.LinuxAppManager"
for asset, destination in (
    ("gui/app.py", "usr/lib/linux-app-manager/app.py"),
    ("packaging/appimage/launcher.py", "usr/lib/linux-app-manager/appimage-launcher.py"),
    ("packaging/appimage/AppRun", "AppRun"),
    (f"packaging/{app_id}.desktop", f"{app_id}.desktop"),
    (f"packaging/{app_id}.png", f"{app_id}.png"),
    (f"packaging/{app_id}.metainfo.xml", f"usr/share/metainfo/{app_id}.appdata.xml"),
    ("LICENSE", "usr/share/licenses/linux-app-manager/LICENSE"),
    ("packaging/appimage/runtime-LICENSE", "usr/share/licenses/appimage-runtime/LICENSE"),
):
    copy_file(source / asset, appdir / destination)
third_party = source / "THIRD_PARTY_LICENSES"
if third_party.is_dir() and (third_party / "inventory.json").is_file():
    copy_tree(third_party, appdir / "usr/share/licenses/linux-app-manager/third-party")
elif os.environ.get("LAM_APPIMAGE_ALLOW_UNSUPPORTED_BUILDER") != "1":
    raise RuntimeError("production source must contain collected THIRD_PARTY_LICENSES/inventory.json")
desktop = appdir / f"{app_id}.desktop"
desktop.write_text(re.sub(r"^Exec=.*$", "Exec=AppRun", desktop.read_text(), flags=re.MULTILINE))
copy_file(desktop, appdir / "usr/share/applications" / desktop.name)
(appdir / ".DirIcon").symlink_to(f"{app_id}.png")
# Associate copied runtime files with Debian package versions and include licenses.
packages = set()
paths = sorted(path for path in copied if not path.startswith(str(source)))
for index in range(0, len(paths), 150):
    result = subprocess.run(["dpkg-query", "-S", *paths[index:index + 150]], text=True, capture_output=True)
    packages.update(parse_dpkg_owners(result.stdout))
inventory = []
for package in sorted(packages):
    version = subprocess.check_output(["dpkg-query", "-W", "-f=${Version}", package], text=True)
    inventory.append({"name": package, "version": version})
    copyright_file = Path("/usr/share/doc") / package.split(":")[0] / "copyright"
    if not copyright_file.is_file():
        raise RuntimeError(f"license missing for bundled package {package}")
    copy_file(copyright_file, appdir / "usr/share/licenses/runtime" / package.replace(":", "_") / "copyright")
pins = json.loads((source / "packaging/appimage/tools.json").read_text())
if hashlib.sha256((source / "packaging/appimage/runtime-LICENSE").read_bytes()).hexdigest() != pins["runtime"]["license_sha256"]:
    raise RuntimeError("AppImage runtime license checksum mismatch")
locked = tomllib.loads((source / "Cargo.lock").read_text())
metadata = {"version": tomllib.loads((source / "Cargo.toml").read_text())["package"]["version"],
            "rustc": subprocess.check_output(["rustc", "--version"], text=True).strip(),
            "cargo": subprocess.check_output(["cargo", "--version"], text=True).strip(),
            "glibc": subprocess.check_output(["getconf", "GNU_LIBC_VERSION"], text=True).strip(),
            "rust_packages": [{key: package[key] for key in ("name", "version", "checksum") if key in package}
                              for package in locked["package"]],
            "builder": Path("/etc/os-release").read_text(), "python": sys.version,
            "runtime_packages": inventory,
            "external_tool_pins": pins,
            "development_builder": os.environ.get("LAM_APPIMAGE_ALLOW_UNSUPPORTED_BUILDER") == "1"}
(appdir / "usr/share/linux-app-manager").mkdir(parents=True, exist_ok=True)
(appdir / "usr/share/linux-app-manager/AppImage.build.json").write_text(json.dumps(metadata, indent=2) + "\n")
