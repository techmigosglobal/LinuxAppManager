use std::collections::HashMap;
use std::path::Path;

use crate::model::{Category, InstalledApplication, Source};
use crate::provider::{run, which, PackageProvider};

pub struct SnapProvider;

const RUNTIMES: &[&str] = &[
    "core",
    "core18",
    "core20",
    "core22",
    "core24",
    "bare",
    "gtk-common-themes",
];

pub fn parse_snap_list(out: &str) -> Vec<InstalledApplication> {
    out.lines()
        .skip(1)
        .filter_map(|l| {
            let f: Vec<&str> = l.split_whitespace().collect();
            if f.len() < 4 || f.last().is_some_and(|n| n.contains("disabled")) {
                return None;
            }
            let mut a = InstalledApplication::new(Source::Snap, f[0]);
            a.version = Some(f[1].to_string());
            a.publisher = f
                .get(4)
                .map(|p| p.trim_end_matches(['✓', '*']).to_string())
                .filter(|p| !p.is_empty());
            a.installed_size =
                std::fs::metadata(format!("/var/lib/snapd/snaps/{}_{}.snap", f[0], f[2]))
                    .ok()
                    .map(|m| m.len());
            a.category = if f[0] == "snapd" {
                Category::SystemComponent
            } else if RUNTIMES.contains(&f[0])
                || f[0].starts_with("gnome-")
                || f[0].starts_with("mesa-")
            {
                Category::Runtime
            } else {
                Category::CliApplication
            }; // upgraded to Desktop when a .desktop entry links to it
            a.system_protected = f[0] == "snapd" || f[0].starts_with("core");
            a.removable = !a.system_protected;
            Some(a)
        })
        .collect()
}

impl PackageProvider for SnapProvider {
    fn source(&self) -> Source {
        Source::Snap
    }
    fn available(&self) -> bool {
        which("snap")
    }
    fn scan(&self) -> Result<Vec<InstalledApplication>, String> {
        Ok(parse_snap_list(&run("snap", &["list"])?))
    }
    fn uninstall_argv(&self, package: &str, clean: bool) -> Vec<String> {
        let mut v = vec!["snap".to_string(), "remove".into()];
        if clean {
            v.push("--purge".into());
        }
        v.push(package.into());
        v
    }
    /// Snap desktop files are named "<snap>_<app>.desktop".
    fn owners_of(&self, paths: &[String]) -> HashMap<String, String> {
        paths
            .iter()
            .filter(|p| p.contains("/snapd/desktop/"))
            .filter_map(|p| {
                Some((
                    p.clone(),
                    Path::new(p)
                        .file_stem()?
                        .to_str()?
                        .split('_')
                        .next()?
                        .to_string(),
                ))
            })
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn parses_list() {
        let out = "Name Version Rev Tracking Publisher Notes\nspotify 1.2.40 80 latest/stable spotify✓ -\ncore22 20240111 1380 latest/stable canonical✓ base\nold 1 2 latest/stable x disabled\n";
        let a = parse_snap_list(out);
        assert_eq!(a.len(), 2);
        assert_eq!(a[0].publisher.as_deref(), Some("spotify"));
        assert_eq!(a[1].category, Category::Runtime);
        assert!(a[1].system_protected);
    }
}
