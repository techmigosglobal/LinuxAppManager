"""Exercise real Debian archives, repository metadata, and GPG verification."""

import getpass
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


apt = load_script("build-apt-repository")
pages = load_script("prepare-pages")
collector = load_script("collect-apt-packages")


class AptRepositoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for tool in ("dpkg-deb", "dpkg", "apt-ftparchive", "gpg", "gpgv", "appstreamcli"):
            if not shutil.which(tool):
                raise RuntimeError(f"repository tests require {tool}")
        cls.temp = tempfile.TemporaryDirectory(prefix="lam-apt-test-")
        cls.root = Path(cls.temp.name)
        cls.gpg_home = cls.root / "gnupg"
        cls.gpg_home.mkdir(mode=0o700)
        cls.previous_home = os.environ.get("GNUPGHOME")
        os.environ["GNUPGHOME"] = str(cls.gpg_home)
        subprocess.run(
            ["gpg", "--batch", "--pinentry-mode", "loopback", "--passphrase", "",
             "--quick-generate-key", "Repository test <test@invalid.local>", "ed25519", "sign", "0"],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        keys = subprocess.check_output(["gpg", "--with-colons", "--list-secret-keys"]).decode()
        cls.fingerprint = next(line.split(":")[9] for line in keys.splitlines() if line.startswith("fpr:"))
        cls.packages = cls.root / "packages"
        for suite in apt.SUITES:
            (cls.packages / suite).mkdir(parents=True)
            for version in ("0.1.9", "0.1.10", "0.2.0"):
                cls.make_package(suite, version)
        cls.repository = cls.root / "repository"
        apt.build(cls.packages, cls.repository, cls.fingerprint)

    @classmethod
    def tearDownClass(cls):
        if cls.previous_home is None:
            os.environ.pop("GNUPGHOME", None)
        else:
            os.environ["GNUPGHOME"] = cls.previous_home
        subprocess.run(["gpgconf", "--homedir", str(cls.gpg_home), "--kill", "gpg-agent"], check=False)
        cls.temp.cleanup()

    @classmethod
    def make_package(cls, suite, version, package_name="linux-app-manager"):
        stage = cls.root / f"stage-{suite}-{version}"
        (stage / "DEBIAN").mkdir(parents=True)
        (stage / "DEBIAN" / "control").write_text(
            f"Package: {package_name}\nVersion: {version}+{suite}\nArchitecture: amd64\n"
            "Maintainer: Test <test@invalid.local>\nDescription: Repository integration fixture\n"
        )
        for relative in (
            f"usr/share/metainfo/{apt.APP_ID}.metainfo.xml",
            f"usr/share/icons/hicolor/512x512/apps/{apt.APP_ID}.png",
        ):
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / "packaging" / Path(relative).name, target)
        output = cls.packages / suite / f"{package_name}_{version}+{suite}_amd64.deb"
        subprocess.run(["dpkg-deb", "--build", "--root-owner-group", str(stage), str(output)],
                       check=True, stdout=subprocess.DEVNULL)
        return output

    def test_keeps_two_newest_versions_using_debian_order(self):
        manifest = json.loads((self.repository / "repository.json").read_text())
        for suite in apt.SUITES:
            self.assertEqual([p["version"] for p in manifest["suites"][suite]],
                             [f"0.2.0+{suite}", f"0.1.10+{suite}"])
            packages = (self.repository / "dists" / suite / "main" / "binary-amd64" / "Packages").read_text()
            self.assertIn(f"0.1.10+{suite}", packages)
            self.assertNotIn(f"0.1.9+{suite}", packages)
            self.assertIn(f"Filename: pool/{suite}/", packages)

    def test_signatures_and_tampering(self):
        for suite in apt.SUITES:
            path = self.repository / "dists" / suite / "InRelease"
            command = ["gpgv", "--keyring", str(self.repository / "vin-linuxmanager.gpg")]
            subprocess.run(command + [str(path)], check=True, stderr=subprocess.DEVNULL)
            tampered = self.root / f"tampered-{suite}"
            tampered.write_bytes(path.read_bytes().replace(b"Origin: VIN-LinuxManager", b"Origin: altered"))
            self.assertNotEqual(subprocess.run(command + [str(tampered)], stderr=subprocess.DEVNULL).returncode, 0)

    def test_catalog_and_explicit_repository_trust(self):
        import gzip
        for suite in apt.SUITES:
            catalog = self.repository / "dists" / suite / "main" / "dep11" / "Components-amd64.yml.gz"
            self.assertIn(apt.APP_ID, gzip.decompress(catalog.read_bytes()).decode())
            self.assertTrue(catalog.with_name("icons-64x64.tar.gz").is_file())
            sources = (self.repository / f"vin-linuxmanager-{suite}.sources").read_text()
            self.assertIn("Signed-By: /etc/apt/keyrings/vin-linuxmanager.gpg", sources)
            self.assertNotIn("Trusted:", sources)

    def test_pages_keep_site_and_repository_together(self):
        output = self.root / "pages"
        pages.prepare(ROOT / "website", self.repository, output)
        self.assertTrue((output / "index.html").is_file())
        self.assertIn("0.2.0+ubuntu24.04", (output / "install.html").read_text())
        self.assertTrue((output / "apt" / "dists" / "ubuntu24.04" / "InRelease").is_file())
        with self.assertRaises(ValueError):
            pages.prepare(ROOT / "website", self.repository, output)

    def test_missing_suite_cannot_replace_repository(self):
        output = self.root / "must-not-exist"
        with self.assertRaises(ValueError):
            apt.build(self.root / "missing", output, self.fingerprint)
        self.assertFalse(output.exists())

    def test_wrong_package_is_rejected(self):
        foreign = self.make_package("ubuntu24.04", "0.3.0", "foreign-package")
        try:
            with self.assertRaises(ValueError):
                apt.inspect_package(foreign)
        finally:
            foreign.unlink()

    def test_real_apt_accepts_signed_index_and_downloads_previous_version(self):
        sandbox = self.root / "apt-client"
        for directory in ("state/lists/partial", "cache/archives/partial", "etc/preferences.d", "log", "downloads"):
            (sandbox / directory).mkdir(parents=True, exist_ok=True)
        (sandbox / "state/status").touch()
        (sandbox / "etc/sources.list").write_text(
            f"deb [arch=amd64 signed-by={self.repository}/vin-linuxmanager.gpg] "
            f"file:{self.repository} ubuntu24.04 main\n"
        )
        config = sandbox / "apt.conf"
        config.write_text(
            f'Dir "{sandbox}";\nDir::State "state";\nDir::State::status "status";\n'
            'Dir::Cache "cache";\nDir::Etc "etc";\nDir::Etc::sourceparts "-";\n'
            'Dir::Etc::trusted "-";\nDir::Etc::trustedparts "-";\nDir::Log "log";\n'
            f'APT::Sandbox::User "{getpass.getuser()}";\nAcquire::Languages "none";\n'
            '#clear APT::Update::Post-Invoke;\n#clear APT::Update::Post-Invoke-Success;\n'
            '#clear DPkg::Post-Invoke;\n#clear DPkg::Pre-Invoke;\n#clear DPkg::Pre-Install-Pkgs;\n'
        )
        subprocess.run(["apt-get", "-c", str(config), "update"], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        policy = subprocess.check_output(["apt-cache", "-c", str(config), "policy", "linux-app-manager"]).decode()
        self.assertIn("Candidate: 0.2.0+ubuntu24.04", policy)
        subprocess.run(["apt-get", "-c", str(config), "download", "linux-app-manager=0.1.10+ubuntu24.04"],
                       cwd=sandbox / "downloads", check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(len(list((sandbox / "downloads").glob("*.deb"))), 1)


class ReleaseSelectionTests(unittest.TestCase):
    def release(self, tag, draft=False):
        names = [f"linux-app-manager_{tag[1:]}+{suite}_amd64.deb" for suite in apt.SUITES]
        return {"tag_name": tag, "draft": draft, "prerelease": False,
                "assets": [{"name": name} for name in names + [name + ".asc" for name in names]
                           + ["SHA256SUMS", "SHA256SUMS.asc"]]}

    def test_selection_uses_versions_and_ignores_drafts_and_legacy(self):
        releases = [self.release("v0.1.9"), self.release("v0.1.10"), self.release("v0.2.0"),
                    self.release("v0.3.0", draft=True),
                    {"tag_name": "v0.1.0", "draft": False, "prerelease": False, "assets": []}]
        self.assertEqual([r["tag_name"] for r in collector.eligible_releases(releases)], ["v0.2.0", "v0.1.10"])

    def test_incomplete_signed_release_cannot_silently_replace_repo(self):
        release = self.release("v0.1.1")
        release["assets"] = [a for a in release["assets"] if a["name"] != "SHA256SUMS.asc"]
        with self.assertRaises(ValueError):
            collector.eligible_releases([release])


if __name__ == "__main__":
    unittest.main()
