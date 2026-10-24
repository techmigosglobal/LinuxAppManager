#!/usr/bin/env python3
"""Boot a checksummed official cloud image and test signed release packages."""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

root = Path(__file__).resolve().parent.parent
target, release_dir, evidence_dir = sys.argv[1:]
release = Path(release_dir).resolve()
version = json.loads((release / "MANIFEST.json").read_text())["version"]
assert re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version)
evidence = Path(evidence_dir).resolve()
evidence.mkdir(parents=True, exist_ok=True)
images = json.loads((root / "packaging/acceptance-images.json").read_text())
image = images[target]
with tempfile.TemporaryDirectory(prefix="lam-acceptance-", dir=os.environ.get("RUNNER_TEMP")) as temporary:
    work = Path(temporary)
    base = work / "base.qcow2"
    digest = hashlib.new(image["algorithm"])
    with urllib.request.urlopen(image["url"], timeout=120) as response, base.open("wb") as output:
        while block := response.read(1024 * 1024):
            digest.update(block)
            output.write(block)
    assert digest.hexdigest() == image["digest"], "official image checksum changed; review a new pin"
    (evidence / "image.json").write_text(json.dumps(image, indent=2) + "\n")
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(work / "key")], check=True)
    public = (work / "key.pub").read_text().strip()
    # The key is generated only for this disposable guest. No publisher secrets
    # or runner tokens enter the VM, cloud-init, evidence or serial console.
    (work / "user-data").write_text(
        "#cloud-config\nusers:\n  - name: lamtest\n    shell: /bin/bash\n"
        "    lock_passwd: true\n    sudo: ALL=(ALL) NOPASSWD:ALL\n"
        f"    ssh_authorized_keys:\n      - {public}\n"
        "ssh_pwauth: false\ndisable_root: true\n"
        "runcmd:\n  - [touch, /run/lam-disposable-acceptance]\n")
    (work / "meta-data").write_text("instance-id: lam-acceptance\nlocal-hostname: lam-acceptance\n")
    subprocess.run(["cloud-localds", str(work / "seed.iso"), str(work / "user-data"), str(work / "meta-data")], check=True)
    subprocess.run(["qemu-img", "create", "-f", "qcow2", "-F", "qcow2", "-b", str(base), str(work / "disk.qcow2")], check=True)
    subprocess.run(["qemu-img", "resize", str(work / "disk.qcow2"), "16G"], check=True)
    accel = "kvm" if os.access("/dev/kvm", os.R_OK | os.W_OK) else "tcg"
    (evidence / "acceleration.txt").write_text(accel + "\n")
    command = ["qemu-system-x86_64", "-machine", f"q35,accel={accel}", "-cpu", "host" if accel == "kvm" else "max",
               "-m", "4096", "-smp", "2", "-display", "none", "-monitor", "none",
               "-serial", f"file:{evidence / 'serial.log'}",
               "-drive", f"file={work / 'disk.qcow2'},format=qcow2,if=virtio",
               "-drive", f"file={work / 'seed.iso'},format=raw,if=virtio,readonly=on",
               "-netdev", "user,id=net0,hostfwd=tcp:127.0.0.1:2222-:22", "-device", "virtio-net-pci,netdev=net0"]
    ssh_options = ["-i", str(work / "key"), "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new",
                   "-o", f"UserKnownHostsFile={work / 'known_hosts'}", "-o", "ConnectTimeout=10"]
    ssh = ["ssh", *ssh_options, "-p", "2222", "lamtest@127.0.0.1"]
    with (evidence / "qemu.log").open("w") as qemu_log:
        vm = subprocess.Popen(command, stdout=qemu_log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 900
            while time.monotonic() < deadline:
                assert vm.poll() is None, "QEMU exited before guest startup"
                if subprocess.run([*ssh, "test -f /run/lam-disposable-acceptance"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
                    break
                time.sleep(5)
            else:
                raise RuntimeError("guest boot/cloud-init timed out")
            upload = work / "acceptance"
            (upload / "packages").mkdir(parents=True)
            for name in ["accept-native-desktop.sh", "accept-polkit-cancel.py", "accept-installed-gui.py", "accept-appimage-launch.py", "smoke-installed.py"]:
                shutil.copy2(root / "scripts" / name, upload / name)
            if target.startswith(("ubuntu", "debian")):
                pattern = f"linux-app-manager_*{target}*_amd64.deb"
            elif target.startswith("fedora"):
                pattern = f"linux-app-manager-[0-9]*.fc{target[6:]}.x86_64.rpm"
            else:
                pattern = "linux-app-manager-[0-9]*-x86_64-arch.pkg.tar.zst"
            matches = list(release.glob(pattern))
            assert len(matches) == 1, matches
            shutil.copy2(matches[0], upload / "packages" / matches[0].name)
            if target in {"ubuntu24.04", "fedora44", "arch"}:
                appimage = release / f"VIN-LinuxManager-{version}-x86_64.AppImage"
                assert appimage.is_file()
                shutil.copy2(appimage, upload / "packages" / appimage.name)
            if target.startswith(("ubuntu", "debian")):
                shutil.copytree(release.parent / "previous", upload / "previous")
            subprocess.run(["scp", *ssh_options, "-P", "2222", "-r", str(upload), "lamtest@127.0.0.1:~/"], check=True)
            with (evidence / "acceptance.log").open("w") as log:
                result = subprocess.run([*ssh, f"sudo env LAM_DISPOSABLE_VM=1 bash /home/lamtest/acceptance/accept-native-desktop.sh {target}"],
                                        stdout=log, stderr=subprocess.STDOUT, timeout=2400)
            print((evidence / "acceptance.log").read_text(), flush=True)
            assert result.returncode == 0, f"guest acceptance failed: {result.returncode}"
            assert f"Desktop VM acceptance passed: {target}" in (evidence / "acceptance.log").read_text()
        finally:
            vm.terminate()
            try:
                vm.wait(timeout=20)
            except subprocess.TimeoutExpired:
                vm.kill()
                vm.wait()
