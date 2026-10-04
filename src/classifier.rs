//! Keeps low-level packages out of the default Applications list (PRD section 11).
use crate::model::Category;
use crate::security::is_protected;

pub fn classify_apt(pkg: &str, section: &str) -> Category {
    if is_protected(pkg) {
        return if pkg.starts_with("linux-image") || pkg.starts_with("linux-modules") {
            Category::KernelComponent
        } else {
            Category::SystemComponent
        };
    }
    let sec = section.rsplit('/').next().unwrap_or("");
    match sec {
        "kernel" => Category::KernelComponent,
        "libs" | "oldlibs" => Category::Library,
        "libdevel" | "devel" => Category::DevelopmentPackage,
        "interpreters" => Category::Runtime,
        "python" | "perl" | "ruby" | "javascript" | "rust" | "golang" | "java" | "haskell"
        | "php" => Category::LanguagePackage,
        "admin" | "base" => Category::SystemComponent,
        _ if pkg.starts_with("lib") => Category::Library,
        "utils" | "net" | "editors" | "text" | "vcs" | "web" | "mail" | "shells" | "science"
        | "math" | "graphics" | "sound" | "video" | "games" => Category::CliApplication,
        _ => Category::Unknown,
    }
}

pub fn classify_rpm(pkg: &str, group: &str) -> Category {
    let p = pkg.to_ascii_lowercase();
    let group = group.to_ascii_lowercase();
    if is_protected(&p) {
        return if p == "kernel" || p.starts_with("kernel-") {
            Category::KernelComponent
        } else {
            Category::SystemComponent
        };
    }
    if p == "kernel" || p.starts_with("kernel-") {
        return Category::KernelComponent;
    }
    if p.starts_with("lib")
        || p.ends_with("-libs")
        || group.contains("system environment/libraries")
    {
        return Category::Library;
    }
    if p.ends_with("-devel") || p.ends_with("-headers") || group.starts_with("development/") {
        return Category::DevelopmentPackage;
    }
    if group.contains("interpreters")
        || ["python", "perl", "ruby", "nodejs", "golang", "java"]
            .iter()
            .any(|n| p.starts_with(n))
    {
        return Category::LanguagePackage;
    }
    if group.starts_with("applications/") {
        return Category::CliApplication;
    }
    if group.starts_with("system environment/") || group.starts_with("system management/") {
        return Category::SystemComponent;
    }
    Category::Unknown
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn apt_classes() {
        assert_eq!(classify_apt("libssl3", "libs"), Category::Library);
        assert_eq!(
            classify_apt("ripgrep", "universe/utils"),
            Category::CliApplication
        );
        assert_eq!(
            classify_apt("linux-image-6.8.0-31-generic", "kernel"),
            Category::KernelComponent
        );
        assert_eq!(classify_apt("systemd", "admin"), Category::SystemComponent);
        assert_eq!(classify_apt("gcc", "devel"), Category::DevelopmentPackage);
        assert_eq!(
            classify_apt("python3-requests", "python"),
            Category::LanguagePackage
        );
    }

    #[test]
    fn rpm_classes() {
        assert_eq!(
            classify_rpm("kernel-core", "System Environment/Kernel"),
            Category::KernelComponent
        );
        assert_eq!(
            classify_rpm("libfoo", "System Environment/Libraries"),
            Category::Library
        );
        assert_eq!(
            classify_rpm("gcc-c++-devel", "Development/Tools"),
            Category::DevelopmentPackage
        );
        assert_eq!(
            classify_rpm("firefox", "Applications/Internet"),
            Category::CliApplication
        );
    }
}
