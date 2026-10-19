#!/usr/bin/env python3
"""Hardlink byte-identical installed license files, retaining every notice path."""
import hashlib
from pathlib import Path
import os
import stat
import sys


def deduplicate(root: Path) -> int:
    if not root.is_dir() or root.is_symlink():
        raise ValueError("expected an installed license directory")
    seen = {}
    linked = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"license directory contains a symlink: {path}")
        if not path.is_file():
            continue
        metadata = path.stat()
        data = path.read_bytes()
        key = (stat.S_IMODE(metadata.st_mode), len(data), hashlib.sha256(data).digest())
        original = seen.get(key)
        if original is None:
            seen[key] = path
            continue
        # Verify byte equality too; a digest alone never changes notice content.
        if original.read_bytes() != data:
            raise ValueError(f"unexpected license digest collision: {path}")
        if original.stat().st_ino != metadata.st_ino:
            path.unlink()
            os.link(original, path)
            linked += 1
    return linked


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: hardlink-license-files.py INSTALLED_LICENSE_DIRECTORY")
    try:
        print(f"Hardlinked {deduplicate(Path(sys.argv[1]))} identical installed license files")
    except (ValueError, OSError) as error:
        sys.exit(str(error))
