"""Snap must launch its tested runtime and retain the read-only store scope."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("prepare_snap", ROOT / "scripts/prepare-snap.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SnapPackagingTests(unittest.TestCase):
    def fixture(self, root, development=False, version="0.1.1"):
        for name in ("usr/bin/lam", "AppRun", "usr/share/linux-app-manager/AppImage.build.json",
                     "io.github.techmigosglobal.LinuxAppManager.desktop",
                     "io.github.techmigosglobal.LinuxAppManager.png"):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"fixture")
        (root / "io.github.techmigosglobal.LinuxAppManager.desktop").write_text(
            "[Desktop Entry]\nExec=AppRun\nIcon=example\nType=Application\nName=VIN-LinuxManager\n")
        report = {"version": version, "development_builder": development}
        (root / "usr/share/linux-app-manager/AppImage.build.json").write_text(json.dumps(report))
        external = root / "runtime-report.json"
        external.write_text(json.dumps(report))
        return external

    def test_launches_bundled_runtime_and_records_read_only_scope(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = self.fixture(root)
            name, version = module.prepare(root, report, "a" * 40)
            import yaml
            metadata = yaml.safe_load((root / "meta/snap.yaml").read_text())
            self.assertEqual((name, version), ("vin-linux-app-manager", "0.1.1"))
            self.assertEqual(metadata["apps"][name]["command"], "AppRun")
            self.assertEqual(metadata["grade"], "devel")
            self.assertEqual(metadata["confinement"], "classic")
            self.assertNotIn("/usr/lib/linux-app-manager", (root / "meta/snap.yaml").read_text())
            desktop = (root / "meta/gui/io.github.techmigosglobal.LinuxAppManager.desktop").read_text()
            self.assertIn("Exec=vin-linux-app-manager", desktop)
            proof = json.loads((root / "usr/share/linux-app-manager/Snap.build.json").read_text())
            self.assertFalse(proof["host_mutations"])
            self.assertEqual(proof["source_commit"], "a" * 40)

    def test_rejects_development_runtime_and_version_mismatch(self):
        for development, version in ((True, "0.1.1"), (False, "0.1.0")):
            with self.subTest(development=development, version=version), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                report = self.fixture(root, development, version)
                with self.assertRaises(ValueError):
                    module.prepare(root, report, "a" * 40)

    def test_rejects_mismatched_report_and_noncommit_reference(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = self.fixture(root)
            with self.assertRaisesRegex(ValueError, "full source commit"):
                module.prepare(root, report, "main")
            report.write_text('{"version":"0.1.1","development_builder":false,"different":true}')
            with self.assertRaisesRegex(ValueError, "unchanged production runtime"):
                module.prepare(root, report, "a" * 40)

    @unittest.skipUnless(shutil.which("patchelf"), "ELF verification requires patchelf")
    def test_elf_uses_core24_loader_and_relocatable_library_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = self.fixture(root)
            executable = root / "usr/bin/lam"
            shutil.copyfile("/usr/bin/true", executable)
            executable.chmod(0o755)
            module.prepare(root, report, "a" * 40)
            loader = subprocess.check_output(["patchelf", "--print-interpreter", str(executable)], text=True).strip()
            self.assertEqual(loader, "/snap/core24/current/lib64/ld-linux-x86-64.so.2")
            rpath = subprocess.check_output(["patchelf", "--print-rpath", str(executable)], text=True)
            self.assertIn("$ORIGIN/../lib", rpath)
            self.assertIn("/snap/core24/current/lib/x86_64-linux-gnu", rpath)
            self.assertNotIn(temporary, rpath)
            if Path(loader).is_file():
                subprocess.run([str(executable)], check=True)

    @unittest.skipUnless(shutil.which("cc"), "object fixture requires a C compiler")
    def test_relocatable_object_files_are_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = self.fixture(root)
            object_file = root / "usr/python.o"
            subprocess.run(["cc", "-x", "c", "-c", "-o", str(object_file), "-"],
                           input="int metadata_fixture;", text=True, check=True)
            before = object_file.read_bytes()
            module.prepare(root, report, "a" * 40)
            self.assertEqual(before, object_file.read_bytes())
