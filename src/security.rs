//! Package-name validation and system-package protection (PRD sections 31, 34, 35).

const PROTECTED_EXACT: &[&str] = &[
    "libc6",
    "dpkg",
    "apt",
    "sudo",
    "bash",
    "coreutils",
    "login",
    "init",
    "gdm3",
    "sddm",
    "lightdm",
    "gnome-shell",
    "e2fsprogs",
    "util-linux",
    "ubuntu-desktop",
    "ubuntu-minimal",
    "shim-signed",
    "mount",
    "passwd",
    "base-files",
    "base-passwd",
    "dbus",
    "network-manager",
    "polkitd",
    "policykit-1",
    "udev",
    "linux-generic",
    "pacman",
    "dnf",
    "rpm",
    "glibc",
    "flatpak",
    "snapd",
    "kernel",
    "gdm",
    "grub2",
    "dracut",
    "networkmanager",
    "polkit",
    "dnf5",
    "fedora-release",
    "fedora-release-common",
    "redhat-release",
    "rhel-release",
    "dbus-broker",
    "selinux-policy",
    "platform-python",
    "centos-stream-release",
    "opensuse-release",
];
const PROTECTED_PREFIX: &[&str] = &[
    "systemd",
    "grub",
    "linux-image",
    "linux-modules",
    "initramfs-tools",
    "libc6",
    "apt",
    "dpkg",
    "kernel",
    "rpm",
    "dnf",
    "dracut",
    "glibc",
    "dbus",
    "polkit",
    "networkmanager",
    "platform-python",
    "selinux-policy",
    "fedora-release",
    "redhat-release",
    "rhel-release",
    "opensuse-release",
    "centos-stream-release",
];

pub fn is_protected(pkg: &str) -> bool {
    let p = pkg.split(':').next().unwrap_or(pkg).to_ascii_lowercase();
    let p = p
        .rsplit_once('.')
        .filter(|(_, arch)| {
            matches!(
                *arch,
                "x86_64"
                    | "x86_64_v2"
                    | "x86_64_v3"
                    | "aarch64"
                    | "noarch"
                    | "i386"
                    | "i486"
                    | "i586"
                    | "i686"
                    | "armv5tel"
                    | "armv6hl"
                    | "armv7hl"
                    | "armv7hnl"
                    | "s390x"
                    | "ppc64"
                    | "ppc64le"
                    | "riscv64"
                    | "loongarch64"
            )
        })
        .map(|(name, _)| name)
        .unwrap_or(&p);
    PROTECTED_EXACT.contains(&p)
        || PROTECTED_PREFIX
            .iter()
            .any(|x| p == *x || p.starts_with(&format!("{x}-")))
}

/// Strict allow-list validation: identifiers are never interpreted by a shell,
/// but we still refuse anything that is not a plausible package/app id.
pub fn validate_package_id(id: &str) -> Result<(), String> {
    let first_ok = id.chars().next().is_some_and(|c| c.is_ascii_alphanumeric());
    let chars_ok = id
        .chars()
        .all(|c| c.is_ascii_alphanumeric() || matches!(c, '.' | '+' | '-' | '_' | ':' | '@'));
    if id.is_empty() || id.len() > 200 || !first_ok || !chars_ok || id.contains("..") {
        return Err(format!("invalid package identifier: {id:?}"));
    }
    Ok(())
}

/// Sandboxed store builds do not have a reviewed host-authority boundary yet.
/// They may inspect inventory, but must never start a host package transaction.
pub fn host_mutations_allowed() -> bool {
    std::env::var_os("FLATPAK_ID").is_none() && std::env::var_os("SNAP").is_none()
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn validation() {
        assert!(validate_package_id("org.mozilla.firefox").is_ok());
        assert!(validate_package_id("libstdc++6:amd64").is_ok());
        for bad in ["", "-rf", "a b", "a;rm", "$(x)", "a/../b", "a`b`", "../x"] {
            assert!(validate_package_id(bad).is_err(), "{bad}");
        }
    }
    #[test]
    fn protection() {
        for p in [
            "libc6",
            "systemd",
            "systemd-sysv",
            "linux-image-6.8.0-31-generic",
            "grub-pc",
            "apt-utils",
            "bash",
        ] {
            assert!(is_protected(p), "{p}");
        }
        for p in [
            "kernel-core.x86_64",
            "glibc.x86_64",
            "NetworkManager",
            "dnf5",
            "rpm-libs",
        ] {
            assert!(is_protected(p), "{p}");
        }
        for p in [
            "firefox",
            "vlc",
            "aptitude",
            "gnome-shell-extension-x",
            "ripgrep",
        ] {
            assert!(!is_protected(p), "{p}");
        }
    }
}
