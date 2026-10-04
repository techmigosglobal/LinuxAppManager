use std::collections::HashMap;

use crate::classifier::classify_apt;
use crate::model::{InstalledApplication, Source};
use crate::provider::{run, which, PackageProvider};
use crate::security::{is_protected, validate_package_id};

pub struct AptProvider;

const FORMAT: &str = r"${Package}\t${Version}\t${Installed-Size}\t${Architecture}\t${db:Status-Abbrev}\t${Section}\t${binary:Summary}\n";

pub fn parse_dpkg_query(out: &str) -> Vec<InstalledApplication> {
    out.lines()
        .filter_map(|line| {
            let f: Vec<&str> = line.split('\t').collect();
            if f.len() < 7 || !f[4].starts_with("ii") {
                return None;
            }
            let mut a = InstalledApplication::new(Source::Apt, f[0]);
            a.version = Some(f[1].to_string());
            a.installed_size = f[2].trim().parse::<u64>().ok().map(|k| k * 1024);
            a.architecture = Some(f[3].to_string());
            a.category = classify_apt(f[0], f[5]);
            a.description = Some(f[6].to_string());
            a.system_protected = is_protected(f[0]);
            a.removable = !a.system_protected;
            Some(a)
        })
        .collect()
}

/// Parses `dpkg-query -S` output: "pkg[, pkg2]: /path".
pub fn parse_owners(out: &str) -> HashMap<String, String> {
    out.lines()
        .filter_map(|l| {
            let (pkgs, path) = l.split_once(": /")?;
            let pkg = pkgs
                .split(',')
                .next()?
                .trim()
                .split(':')
                .next()?
                .to_string();
            Some((format!("/{}", path.trim()), pkg))
        })
        .collect()
}

/// Parses `apt-get -s remove` output into the packages that would be removed.
pub fn parse_simulation(out: &str) -> Vec<String> {
    out.lines()
        .filter_map(|l| {
            let l = l
                .strip_prefix("Remv ")
                .or_else(|| l.strip_prefix("Purg "))?;
            Some(l.split_whitespace().next()?.to_string())
        })
        .collect()
}

fn preview_contains_package(preview: &[String], package: &str) -> bool {
    let package_base = package.split(':').next().unwrap_or(package);
    preview
        .iter()
        .any(|item| item == package || item.split(':').next().unwrap_or(item) == package_base)
}

impl AptProvider {
    /// Dependency-safety preview: everything APT would remove alongside `pkg` (PRD section 30).
    pub fn removal_preview(&self, pkg: &str, clean: bool) -> Result<Vec<String>, String> {
        validate_package_id(pkg)?;
        let action = if clean { "purge" } else { "remove" };
        let preview = parse_simulation(&run("apt-get", &["-s", action, pkg])?);
        if !preview_contains_package(&preview, pkg) {
            return Err(
                "APT did not return a complete removal simulation for the selected package".into(),
            );
        }
        Ok(preview)
    }
}

impl PackageProvider for AptProvider {
    fn source(&self) -> Source {
        Source::Apt
    }
    fn available(&self) -> bool {
        which("dpkg-query")
    }
    fn requires_elevation(&self) -> bool {
        true
    }
    fn scan(&self) -> Result<Vec<InstalledApplication>, String> {
        Ok(parse_dpkg_query(&run("dpkg-query", &["-W", "-f", FORMAT])?))
    }
    fn uninstall_argv(&self, package: &str, clean: bool) -> Vec<String> {
        vec![
            "apt-get".into(),
            if clean { "purge" } else { "remove" }.into(),
            "-y".into(),
            package.into(),
        ]
    }
    fn removal_preview(&self, pkg: &str, clean: bool) -> Result<Vec<String>, String> {
        AptProvider::removal_preview(self, pkg, clean)
    }
    fn owners_of(&self, paths: &[String]) -> HashMap<String, String> {
        let mut args: Vec<&str> = vec!["-S"];
        args.extend(paths.iter().map(String::as_str));
        run("dpkg-query", &args)
            .map(|o| parse_owners(&o))
            .unwrap_or_default()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn parses_dpkg() {
        let out = "vlc\t3.0.20\t3400\tamd64\tii \tuniverse/video\tmultimedia player\nold\t1\t5\tall\trc \tutils\tremoved\n";
        let a = parse_dpkg_query(out);
        assert_eq!(a.len(), 1);
        assert_eq!(a[0].installed_size, Some(3400 * 1024));
    }
    #[test]
    fn parses_owners_and_sim() {
        let o = parse_owners("firefox: /usr/share/applications/firefox.desktop\ndpkg-query: no path found matching pattern /x\n");
        assert_eq!(o["/usr/share/applications/firefox.desktop"], "firefox");
        assert_eq!(
            parse_simulation("Remv vlc [3.0] [x]\nInst y\nPurg vlc-data [3.0]\n"),
            vec!["vlc", "vlc-data"]
        );
    }
    #[test]
    fn plans_and_blocks() {
        let p = AptProvider;
        let mut a = InstalledApplication::new(Source::Apt, "vlc");
        assert_eq!(
            p.plan_uninstall(&a, true).unwrap(),
            vec!["apt-get", "purge", "-y", "vlc"]
        );
        a.package_name = Some("bash".into());
        assert!(p.plan_uninstall(&a, false).is_err());
        a.package_name = Some("x; rm -rf /".into());
        assert!(p.plan_uninstall(&a, false).is_err());
    }
}
