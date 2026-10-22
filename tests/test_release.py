"""Release correctness checks: immutable source, relocatable checksums, signature failure."""
import json
import os
import pathlib
import shutil
import subprocess
import tarfile
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent


def run(*args, cwd=None, env=None, check=True):
    result = subprocess.run([str(arg) for arg in args], cwd=cwd, env=env,
                            text=True, capture_output=True, timeout=90)
    if check and result.returncode:
        raise AssertionError(f"command failed: {args}\n{result.stdout}\n{result.stderr}")
    return result


class ReleaseManifestTests(unittest.TestCase):
    def test_checksums_and_manifest_survive_directory_relocation(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = pathlib.Path(temporary)
            artifacts = workspace / "original release"
            (artifacts / "packages").mkdir(parents=True)
            (artifacts / "packages" / "app test.deb").write_bytes(b"package bytes")
            run(ROOT / "scripts/write-release-manifest.sh", artifacts)
            manifest = json.loads((artifacts / "MANIFEST.json").read_text())
            self.assertIn("packages/app test.deb", [a["path"] for a in manifest["artifacts"]])
            self.assertIn("SBOM.cargo.json", (artifacts / "SHA256SUMS").read_text())
            self.assertIn("MANIFEST.json", (artifacts / "SHA256SUMS").read_text())
            destination = workspace / "download"
            shutil.move(artifacts, destination)
            run("sha256sum", "--check", "--strict", "SHA256SUMS", cwd=destination)
            (destination / "packages" / "app test.deb").write_bytes(b"tampered")
            self.assertNotEqual(run("sha256sum", "-c", "SHA256SUMS", cwd=destination, check=False).returncode, 0)

    def test_separate_manifest_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            artifacts = pathlib.Path(temporary) / "artifacts"
            artifacts.mkdir()
            (artifacts / "app.deb").write_bytes(b"x")
            result = run(ROOT / "scripts/write-release-manifest.sh", artifacts,
                         pathlib.Path(temporary) / "other", check=False)
            self.assertNotEqual(result.returncode, 0)

    @unittest.skipUnless(shutil.which("gpg"), "GnuPG unavailable")
    def test_signatures_validate_and_reject_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = pathlib.Path(temporary)
            home = base / "gnupg"
            home.mkdir(mode=0o700)
            env = {**os.environ, "GNUPGHOME": str(home)}
            try:
                run("gpg", "--batch", "--pinentry-mode", "loopback", "--passphrase", "",
                    "--quick-generate-key", "Release Test <release@example.test>",
                    "ed25519", "sign", "1d", env=env)
                output = run("gpg", "--batch", "--with-colons", "--list-secret-keys", env=env).stdout
                fingerprint = next(line.split(":")[9] for line in output.splitlines() if line.startswith("fpr:"))
                artifacts = base / "release"
                artifacts.mkdir()
                (artifacts / "app.deb").write_bytes(b"package")
                key = artifacts / "vin-linuxmanager-release-public-key.asc"
                key.write_text(run("gpg", "--armor", "--export", fingerprint, env=env).stdout)
                run(ROOT / "scripts/write-release-manifest.sh", artifacts, env=env)
                run(ROOT / "scripts/sign-release.sh", fingerprint, artifacts, env=env)
                self.assertTrue((artifacts / f"{key.name}.asc").exists())
                run(ROOT / "scripts/verify-release-signatures.sh", key, artifacts, env=env)
                (artifacts / "app.deb").write_bytes(b"corrupted")
                self.assertNotEqual(run(ROOT / "scripts/verify-release-signatures.sh", key,
                                         artifacts, env=env, check=False).returncode, 0)
            finally:
                run("gpgconf", "--homedir", home, "--kill", "all", check=False)


class SourceArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = pathlib.Path(self.temporary.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        for directory in ["scripts", "debian", "rpm", "arch", "snap", "packaging"]:
            (self.repo / directory).mkdir()
        for script in ["build-source.sh", "check-release-version.py", "collect-vendor-licenses.py"]:
            shutil.copy2(ROOT / "scripts" / script, self.repo / "scripts" / script)
        (self.repo / "Cargo.toml").write_text('[package]\nname = "test-app"\nversion = "1.2.3"\n')
        (self.repo / "Cargo.lock").write_text('version = 4\n[[package]]\nname = "test-app"\nversion = "1.2.3"\n')
        (self.repo / "debian/changelog").write_text("test-app (1.2.3) unstable; urgency=medium\n")
        (self.repo / "rpm/linux-app-manager.spec").write_text("Version: 1.2.3\n")
        (self.repo / "arch/PKGBUILD").write_text("pkgver=1.2.3\n")
        (self.repo / "snap/snapcraft.yaml").write_text("version: '1.2.3'\n")
        (self.repo / "packaging/io.github.techmigosglobal.LinuxAppManager.metainfo.xml").write_text(
            '<component><releases><release version="1.2.3"/></releases></component>')
        (self.repo / "marker").write_text("tag contents\n")
        run("git", "init", "-q", self.repo)
        run("git", "-C", self.repo, "add", ".")
        run("git", "-C", self.repo, "-c", "user.name=Release Test", "-c", "user.email=release@example.test",
            "commit", "-qm", "fixture")
        run("git", "-C", self.repo, "tag", "v1.2.3")
        fake_bin = self.base / "bin"
        fake_bin.mkdir()
        cargo = fake_bin / "cargo"
        cargo.write_text('''#!/usr/bin/env python3
import pathlib, sys
if sys.argv[1] == "vendor":
    crate = pathlib.Path("vendor/test-dependency")
    crate.mkdir(parents=True)
    (crate / "source").write_text("locked fixture\\n")
    (crate / "Cargo.toml").write_text('[package]\\nname = "test-dependency"\\nversion = "1.0.0"\\nlicense = "MIT"\\n')
    (crate / "LICENSE").write_text("Fixture license text preserved exactly.\\n")
    print('[source.crates-io]\\nreplace-with = "vendored-sources"\\n[source.vendored-sources]\\ndirectory = "vendor"')
else:
    print("{}")
''')
        cargo.chmod(0o755)
        self.env = {**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"}

    def test_official_bundle_uses_tag_not_worktree_and_is_deterministic(self):
        (self.repo / "marker").write_text("unreleased work\n")
        first, second = self.base / "first", self.base / "second"
        script = self.repo / "scripts/build-source.sh"
        run(script, "v1.2.3", first, env=self.env)
        run(script, "v1.2.3", second, env=self.env)
        name = "linux-app-manager-1.2.3.tar.gz"
        self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())
        with tarfile.open(first / name) as archive:
            prefix = "linux-app-manager-1.2.3/"
            self.assertEqual(archive.extractfile(prefix + "marker").read(), b"tag contents\n")
            self.assertIn(prefix + "vendor/test-dependency/source", archive.getnames())
            self.assertIn(prefix + ".cargo/config.toml", archive.getnames())
            self.assertEqual(archive.extractfile(prefix + "THIRD_PARTY_LICENSES/test-dependency/LICENSE").read(),
                             b"Fixture license text preserved exactly.\n")
            self.assertIn(prefix + "THIRD_PARTY_LICENSES/inventory.json", archive.getnames())
            origin = json.load(archive.extractfile(prefix + "source-origin.json"))
            self.assertEqual(origin["ref"], "v1.2.3")
            self.assertFalse(origin["local_worktree"])

    def test_local_mode_is_explicit_and_records_worktree(self):
        (self.repo / "marker").write_text("working changes\n")
        output = self.base / "local"
        run(self.repo / "scripts/build-source.sh", "--local", output, env=self.env)
        with tarfile.open(output / "linux-app-manager-1.2.3.tar.gz") as archive:
            prefix = "linux-app-manager-1.2.3/"
            self.assertEqual(archive.extractfile(prefix + "marker").read(), b"working changes\n")
            self.assertTrue(json.load(archive.extractfile(prefix + "source-origin.json"))["local_worktree"])

    def test_mutable_ref_and_mismatched_metadata_are_rejected(self):
        script = self.repo / "scripts/build-source.sh"
        self.assertNotEqual(run(script, "HEAD", self.base / "invalid", env=self.env, check=False).returncode, 0)
        (self.repo / "snap/snapcraft.yaml").write_text("version: '0.0.0'\n")
        result = run(self.repo / "scripts/check-release-version.py", "--root", self.repo, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("snap/snapcraft.yaml", result.stderr)

    def test_version_and_tag_identity_checks(self):
        script = self.repo / "scripts/check-release-version.py"
        run(script, "--root", self.repo, "--tag", "v1.2.3", "--version", "1.2.3")
        self.assertNotEqual(run(script, "--root", self.repo, "--version", "1.2.4", check=False).returncode, 0)
        self.assertNotEqual(run(script, "--root", self.repo, "--tag", "main", check=False).returncode, 0)
        run("git", "-C", self.repo, "-c", "user.name=Release Test", "-c", "user.email=release@example.test",
            "commit", "--allow-empty", "-qm", "different head")
        self.assertNotEqual(run(script, "--root", self.repo, "--tag", "v1.2.3", check=False).returncode, 0)


if __name__ == "__main__":
    unittest.main()
