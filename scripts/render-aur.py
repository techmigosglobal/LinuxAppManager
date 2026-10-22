#!/usr/bin/env python3
"""Render the AUR release recipe from the actual offline source archive."""
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile


def render(archive: Path, output: Path) -> None:
    match = re.fullmatch(r"linux-app-manager-(\d+\.\d+\.\d+)\.tar\.gz", archive.name)
    if not match:
        raise ValueError("source archive must be named linux-app-manager-VERSION.tar.gz")
    version = match[1]
    expected = f"linux-app-manager-{version}"
    with tarfile.open(archive) as source:
        names = {member.name.rstrip("/") for member in source}
    for required in ("Cargo.lock", "LICENSE", "vendor", ".cargo/config.toml"):
        if not any(name == f"{expected}/{required}" or name.startswith(f"{expected}/{required}/") for name in names):
            raise ValueError(f"archive is missing {required}")
    if not shutil.which("makepkg"):
        raise RuntimeError("makepkg is required to generate authoritative .SRCINFO")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    template = Path(__file__).resolve().parents[1] / "arch/PKGBUILD.in"
    recipe = template.read_text().replace("@VERSION@", version).replace("@SHA256@", digest)
    output.mkdir(parents=True, exist_ok=True)
    (output / "PKGBUILD").write_text(recipe)
    result = subprocess.run(["makepkg", "--printsrcinfo", "-p", "PKGBUILD"], cwd=output, check=True, text=True, capture_output=True)
    (output / ".SRCINFO").write_text(result.stdout)
    print(f"Rendered AUR recipe for {version}; source sha256 {digest}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: render-aur.py SOURCE_ARCHIVE OUTPUT_DIR")
    try:
        render(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
    except (ValueError, RuntimeError, OSError, tarfile.TarError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
