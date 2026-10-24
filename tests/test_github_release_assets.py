"""Regression for GitHub changing Debian '~' download names after signing."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
RELEASE_TAG = "v" + tomllib.loads((ROOT / "Cargo.toml").read_text())["package"]["version"]
spec = importlib.util.spec_from_file_location("release_assets", ROOT / "scripts/github-release-assets.py")
assets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assets)


class AssetNamesTests(unittest.TestCase):
    def test_normalize_before_signing_preserves_package_bytes(self):
        with tempfile.TemporaryDirectory() as work:
            directory = Path(work)
            (directory / "app_1~ubuntu24.04.deb").write_bytes(b"real package bytes")
            assets.prepare(directory)
            self.assertEqual((directory / "app_1.ubuntu24.04.deb").read_bytes(), b"real package bytes")
            self.assertFalse((directory / "app_1~ubuntu24.04.deb").exists())

    def test_collision_is_rejected_before_any_rename(self):
        with tempfile.TemporaryDirectory() as work:
            directory = Path(work)
            for name in ("app~1.deb", "app.1.deb"):
                (directory / name).write_bytes(b"bytes")
            with self.assertRaisesRegex(ValueError, "collision"):
                assets.prepare(directory)
            self.assertEqual(len(list(directory.iterdir())), 2)
            self.assertTrue((directory / "app~1.deb").exists())

    def test_hosted_names_sizes_and_digests_must_match(self):
        with tempfile.TemporaryDirectory() as work:
            directory = Path(work)
            (directory / "app~1.deb").write_bytes(b"package")
            release = {"draft": True, "assets": [{"name": "app.1.deb", "size": 7,
                       "digest": "sha256:" + hashlib.sha256(b"package").hexdigest()}]}
            with self.assertRaisesRegex(ValueError, "names differ"):
                assets.check_hosted(directory, release)
            assets.prepare(directory)
            assets.check_hosted(directory, release)
            release["draft"] = False
            with self.assertRaisesRegex(ValueError, "requires a draft"):
                assets.check_hosted(directory, release)
            assets.check_hosted(directory, release, require_draft=False)
            release["assets"][0]["digest"] = "sha256:" + "0" * 64
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                assets.check_hosted(directory, release, require_draft=False)

    @unittest.skipUnless(shutil.which("gpg") and shutil.which("gpgv"), "GnuPG required")
    def test_repair_preserves_verified_binary_and_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as work:
            base = Path(work)
            home = base / "gnupg"
            home.mkdir(mode=0o700)
            env = {**os.environ, "GNUPGHOME": str(home), "RELEASE_TAG": RELEASE_TAG}

            def run(*args, env=env):
                return subprocess.check_output([str(a) for a in args], env=env, stderr=subprocess.PIPE, text=True)

            try:
                run("gpg", "--batch", "--pinentry-mode", "loopback", "--passphrase", "",
                    "--quick-generate-key", "Download Test <test@invalid.local>", "ed25519", "sign", "1d")
                fingerprint = next(line.split(":")[9] for line in run("gpg", "--with-colons", "--list-secret-keys").splitlines() if line.startswith("fpr:"))
                directory = base / "release"
                directory.mkdir()
                original_name = "app_0.1.1~ubuntu24.04.deb"
                (directory / original_name).write_bytes(b"verified original binary")
                key = directory / "vin-linuxmanager-release-public-key.asc"
                key.write_text(run("gpg", "--armor", "--export", fingerprint))
                run(ROOT / "scripts/write-release-manifest.sh", directory)
                run(ROOT / "scripts/sign-release.sh", fingerprint, directory)
                original_manifest = (directory / "MANIFEST.json").read_bytes()
                identity = json.loads(original_manifest)
                keyring = base / "trusted.gpg"
                run("gpg", "--batch", "--dearmor", "--output", keyring, key)
                # The actual observed upload behavior: rename both asset and signature.
                for path in list(directory.iterdir()):
                    path.rename(directory / path.name.replace("~", "."))
                with self.assertRaises(subprocess.CalledProcessError):
                    run(ROOT / "scripts/verify-release-signatures.sh", key, directory)
                binary = directory / original_name.replace("~", ".")
                binary.write_bytes(b"tampered")
                with self.assertRaisesRegex(ValueError, "original signed bytes changed"):
                    assets.repair(directory, keyring, RELEASE_TAG, identity["commit"])
                self.assertEqual((directory / "MANIFEST.json").read_bytes(), original_manifest)
                binary.write_bytes(b"verified original binary")
                original_signature = Path(str(binary) + ".asc").read_bytes()
                self.assertEqual(assets.repair(directory, keyring, RELEASE_TAG, identity["commit"]), 1)
                for name in ("MANIFEST.json", "SHA256SUMS"):
                    run("gpg", "--batch", "--yes", "--armor", "--detach-sign", "--local-user", fingerprint,
                        "--output", directory / (name + ".asc"), directory / name)
                run(ROOT / "scripts/verify-release-signatures.sh", key, directory)
                self.assertEqual(Path(str(binary) + ".asc").read_bytes(), original_signature)
                self.assertEqual(json.loads((directory / "MANIFEST.json").read_text())["commit"], identity["commit"])
            finally:
                subprocess.run(["gpgconf", "--homedir", str(home), "--kill", "all"], capture_output=True)


if __name__ == "__main__":
    unittest.main()
