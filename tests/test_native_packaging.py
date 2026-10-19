"""Release recipe contracts and failure behavior, independent of host builders."""
import hashlib
import importlib.util
import io
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("render_aur", ROOT / "scripts/render-aur.py")
render_aur = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render_aur)
license_spec = importlib.util.spec_from_file_location("collect_vendor_licenses", ROOT / "scripts/collect-vendor-licenses.py")
licenses = importlib.util.module_from_spec(license_spec)
license_spec.loader.exec_module(licenses)


class NativePackaging(unittest.TestCase):
    def archive(self, directory, filename="linux-app-manager-0.1.1.tar.gz", omitted=None):
        archive = Path(directory, filename)
        with tarfile.open(archive, "w:gz") as tar:
            for name in ("Cargo.lock", "LICENSE", "vendor/example/Cargo.toml", ".cargo/config.toml"):
                if name == omitted:
                    continue
                item = tarfile.TarInfo("linux-app-manager-0.1.1/" + name)
                payload = b"release fixture\n"
                item.size = len(payload)
                tar.addfile(item, io.BytesIO(payload))
        return archive

    def test_aur_uses_actual_release_digest_and_immutable_asset(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = self.archive(temporary)
            output = Path(temporary, "aur")
            fake = subprocess.CompletedProcess([], 0, "pkgbase = linux-app-manager\n\tpkgver = 0.1.1\n", "")
            with patch.object(render_aur.shutil, "which", return_value="/usr/bin/makepkg"), patch.object(render_aur.subprocess, "run", return_value=fake) as makepkg:
                render_aur.render(archive, output)
            recipe = (output / "PKGBUILD").read_text()
            self.assertIn(hashlib.sha256(archive.read_bytes()).hexdigest(), recipe)
            self.assertIn("/releases/download/v${pkgver}/", recipe)
            self.assertNotIn("SKIP", recipe)
            self.assertNotIn("git+", recipe)
            self.assertEqual((output / ".SRCINFO").read_text(), fake.stdout)
            self.assertEqual(makepkg.call_args.args[0], ["makepkg", "--printsrcinfo", "-p", "PKGBUILD"])

    def test_unvendored_archive_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = self.archive(temporary, omitted=".cargo/config.toml")
            with self.assertRaisesRegex(ValueError, "missing .cargo/config.toml"):
                render_aur.render(archive, Path(temporary, "out"))

    def test_aur_metadata_requires_real_makepkg(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = self.archive(temporary)
            with patch.object(render_aur.shutil, "which", return_value=None):
                with self.assertRaisesRegex(RuntimeError, "makepkg is required"):
                    render_aur.render(archive, Path(temporary, "out"))

    def test_unknown_build_target_fails_before_any_build(self):
        result = subprocess.run([str(ROOT / "scripts/build-native.sh"), "unsupported", "/tmp/missing-source.tar.gz", "/tmp/unused-output"], text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsupported native build target", result.stderr)

    def test_all_native_recipes_require_offline_locked_cargo_and_license(self):
        for filename in ("debian/rules", "rpm/linux-app-manager.spec", "arch/PKGBUILD.in"):
            with self.subTest(recipe=filename):
                recipe = (ROOT / filename).read_text()
                self.assertIn("--locked --offline", recipe)
                self.assertIn("LICENSE", recipe)
                self.assertIn("cargo test --all-targets", recipe)

    def test_debian_and_rpm_declare_c_compiler_for_bundled_sqlite(self):
        self.assertIn("gcc", (ROOT / "debian/control").read_text())
        self.assertIn("BuildRequires:  gcc", (ROOT / "rpm/linux-app-manager.spec").read_text())


class VendorLicenses(unittest.TestCase):
    def crate(self, root, license_id="MIT", license_file=None):
        crate = root / "vendor" / "example-1.2.3"
        crate.mkdir(parents=True)
        manifest = '[package]\nname="example"\nversion="1.2.3"\nauthors=["Example Author"]\n'
        if license_id:
            manifest += 'license="' + license_id + '"\n'
        if license_file:
            manifest += 'license-file="' + license_file + '"\n'
        (crate / "Cargo.toml").write_text(manifest)
        return crate

    def test_exact_nested_license_notices_and_deterministic_attribution(self):
        import json
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            crate = self.crate(root)
            exact = b"MIT upstream copyright\r\nExact license bytes\r\n"
            (crate / "LICENSE-MIT").write_bytes(exact)
            (crate / "nested").mkdir()
            (crate / "nested" / "NOTICE.txt").write_bytes(b"nested attribution\n")
            output = licenses.collect(root)
            self.assertEqual((output / crate.name / "LICENSE-MIT").read_bytes(), exact)
            self.assertEqual((output / crate.name / "nested" / "NOTICE.txt").read_bytes(), b"nested attribution\n")
            before = (output / "inventory.json").read_bytes()
            metadata = json.loads(before)["packages"][0]
            self.assertEqual(metadata["license"], "MIT")
            self.assertEqual(metadata["authors"], ["Example Author"])
            self.assertEqual(metadata["version"], "1.2.3")
            licenses.collect(root)
            self.assertEqual((output / "inventory.json").read_bytes(), before)

    def test_notice_without_license_text_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            crate = self.crate(root)
            (crate / "NOTICE").write_text("copyright attribution only")
            with self.assertRaisesRegex(ValueError, "no upstream license text"):
                licenses.collect(root)
            self.assertFalse((root / "THIRD_PARTY_LICENSES").exists())

    def test_declared_custom_license_file_is_copied(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            crate = self.crate(root, license_id=None, license_file="legal/terms.txt")
            (crate / "legal").mkdir()
            (crate / "legal" / "terms.txt").write_bytes(b"exact custom license\n")
            output = licenses.collect(root)
            self.assertEqual((output / crate.name / "legal" / "terms.txt").read_bytes(), b"exact custom license\n")

    def test_declared_license_outside_crate_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.crate(root, license_id=None, license_file="../../outside.txt")
            (root / "outside.txt").write_text("outside crate")
            with self.assertRaisesRegex(ValueError, "invalid or missing license-file"):
                licenses.collect(root)


if __name__ == "__main__":
    unittest.main()
