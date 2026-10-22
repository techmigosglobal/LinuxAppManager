#!/usr/bin/env python3
"""Compose website and a freshly verified APT repository into one Pages tree."""

import argparse
import html
import json
from pathlib import Path
import re
import shutil


def prepare(website, repository, output):
    if output.exists():
        raise ValueError("Pages output must be a new directory")
    manifest = json.loads((repository / "repository.json").read_text())
    for suite in manifest["suites"]:
        if not (repository / "dists" / suite / "InRelease").is_file():
            raise ValueError(f"missing signed suite: {suite}")
    shutil.copytree(website, output, ignore=shutil.ignore_patterns("apt", "__pycache__", "*.pyc"))
    shutil.copytree(repository, output / "apt")
    published = "<p>The signed APT repository is available for these x86_64 suites:</p><ul>"
    for suite, packages in manifest["suites"].items():
        published += f"<li>{html.escape(suite)}: {html.escape(packages[0]['version'])}</li>"
    published += '</ul><p>Verify the signing fingerprint and follow the installation guide before enabling a suite.</p>'
    install = output / "install.html"
    install.write_text(re.sub(r"<!-- APT_STATUS_START -->.*?<!-- APT_STATUS_END -->",
                             published, install.read_text(), flags=re.S))
    index = output / "index.html"
    index.write_text(index.read_text().replace("Staged for testing", "APT repository available"))
    (output / ".nojekyll").touch()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--website", type=Path, required=True)
    parser.add_argument("--apt-repository", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.website, args.apt_repository, args.output)
