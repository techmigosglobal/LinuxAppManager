//! RPM inventory and removal support through DNF.
use std::collections::{HashMap, HashSet};

use crate::classifier::classify_rpm;
use crate::model::{InstalledApplication, Source};
use crate::provider::{run, which, PackageProvider};
use crate::security::{is_protected, validate_package_id};

pub struct DnfProvider;

const RPM_FORMAT: &str = "%{NAME}\t%{VERSION}-%{RELEASE}\t%{SIZE}\t%{ARCH}\t%{GROUP}\t%{SUMMARY}\n";
const RPM_OWNERS_FORMAT: &str = "[%{=NAME}\t%{FILENAMES}\n]";
const RPM_ARCHES: &[&str] = &[
    "x86_64",
    "x86_64_v2",
    "x86_64_v3",
    "aarch64",
    "noarch",
    "i386",
    "i486",
    "i586",
    "i686",
    "armv5tel",
    "armv6hl",
    "armv7hl",
    "armv7hnl",
    "s390x",
    "ppc64",
    "ppc64le",
    "riscv64",
    "loongarch64",
];

pub fn parse_rpm_query(out: &str) -> Vec<InstalledApplication> {
    out.lines()
        .filter_map(|line| {
            let fields: Vec<&str> = line.split('\t').collect();
            if fields.len() < 6 || fields[0].is_empty() || fields[0] == "(none)" {
                return None;
            }
            let mut app = InstalledApplication::new(Source::Dnf, fields[0]);
            app.version = Some(fields[1].to_string()).filter(|v| !v.is_empty() && v != "(none)");
            app.installed_size = fields[2].parse::<u64>().ok().filter(|size| *size > 0);
            app.architecture =
                Some(fields[3].to_string()).filter(|v| !v.is_empty() && v != "(none)");
            app.id = format!("dnf:{}:{}:{}", fields[0], fields[1], fields[3]);
            app.category = classify_rpm(fields[0], fields[4]);
            app.description =
                Some(fields[5].to_string()).filter(|v| !v.is_empty() && v != "(none)");
            app.system_protected = is_protected(fields[0]);
            app.removable = !app.system_protected;
            Some(app)
        })
        .collect()
}

/// Reads package names from DNF's non-mutating `--assumeno` transaction table.
pub fn parse_dnf_removal_preview(out: &str) -> Vec<String> {
    let mut in_removal_section = false;
    let mut seen = HashSet::new();
    let mut packages = Vec::new();

    for line in out.lines() {
        let line = line.trim();
        if line.starts_with("Transaction Summary") || line.starts_with("Operation aborted") {
            in_removal_section = false;
            continue;
        }
        if line == "Removing:"
            || line.starts_with("Removing dependent packages:")
            || line == "Erasing:"
        {
            in_removal_section = true;
            continue;
        }
        if line.starts_with("Installing")
            || line.starts_with("Updating")
            || line.starts_with("Downgrading")
        {
            in_removal_section = false;
            continue;
        }
        if !in_removal_section
            || line.is_empty()
            || line.starts_with("Package ")
            || line.starts_with("====")
        {
            continue;
        }
        let columns: Vec<&str> = line.split_whitespace().collect();
        let Some(name) = columns.first().copied() else {
            continue;
        };
        if name == "Package" || validate_package_id(name).is_err() {
            continue;
        }
        let package = match (
            columns.get(1).filter(|arch| RPM_ARCHES.contains(arch)),
            columns.get(2),
        ) {
            (Some(arch), Some(version)) if !version.starts_with('@') => {
                format!("{name}-{version}.{arch}")
            }
            (Some(arch), _) => format!("{name}.{arch}"),
            _ => name.to_string(),
        };
        if seen.insert(package.clone()) {
            packages.push(package);
        }
    }
    packages
}

fn preview_contains_package(preview: &[String], package: &str) -> bool {
    preview.iter().any(|item| {
        item == package
            || item.rsplit_once('.').is_some_and(|(nevra, arch)| {
                RPM_ARCHES.contains(&arch)
                    && (nevra == package || package.starts_with(&format!("{nevra}-")))
            })
    })
}

impl PackageProvider for DnfProvider {
    fn source(&self) -> Source {
        Source::Dnf
    }
    fn available(&self) -> bool {
        which("dnf") && which("rpm")
    }

    fn scan(&self) -> Result<Vec<InstalledApplication>, String> {
        Ok(parse_rpm_query(&run(
            "rpm",
            &["-qa", "--queryformat", RPM_FORMAT],
        )?))
    }

    fn uninstall_argv(&self, package: &str, _clean: bool) -> Vec<String> {
        vec!["dnf".into(), "remove".into(), "-y".into(), package.into()]
    }

    fn package_argument(&self, app: &InstalledApplication) -> Result<String, String> {
        let package = app
            .package_name
            .as_deref()
            .ok_or("this item has no package name")?;
        match (app.version.as_deref(), app.architecture.as_deref()) {
            (Some(version), Some(architecture)) => {
                Ok(format!("{package}-{version}.{architecture}"))
            }
            (None, Some(architecture)) => Ok(format!("{package}.{architecture}")),
            _ => Ok(package.to_string()),
        }
    }

    fn uninstall_argv_for(&self, app: &InstalledApplication, clean: bool) -> Vec<String> {
        let package = self.package_argument(app).unwrap_or_default();
        self.uninstall_argv(&package, clean)
    }

    fn requires_elevation(&self) -> bool {
        true
    }

    fn removal_preview(&self, package: &str, _clean: bool) -> Result<Vec<String>, String> {
        validate_package_id(package)?;
        if !std::path::Path::new("/usr/bin/pkexec").is_file() {
            return Err("pkexec is required for a DNF transaction preview".into());
        }
        let output = run(
            "/usr/bin/pkexec",
            &["/usr/bin/dnf", "remove", "--assumeno", package],
        )?;
        if !output.contains("Operation aborted") {
            return Err("DNF did not return a complete non-mutating removal preview".into());
        }
        let preview = parse_dnf_removal_preview(&output);
        if preview.is_empty() {
            return Err("DNF returned no package list for the removal transaction".into());
        }
        if !preview_contains_package(&preview, package) {
            return Err("DNF's removal preview did not include the selected package".into());
        }
        Ok(preview)
    }

    fn owners_of(&self, paths: &[String]) -> HashMap<String, String> {
        if paths.is_empty() {
            return HashMap::new();
        }
        let requested: HashSet<&str> = paths.iter().map(String::as_str).collect();
        let mut args = vec!["-qf", "--queryformat", RPM_OWNERS_FORMAT];
        args.extend(paths.iter().map(String::as_str));
        let Ok(output) = run("rpm", &args) else {
            return HashMap::new();
        };
        let mut owners = HashMap::new();
        for line in output.lines() {
            let Some((name, path)) = line.split_once('\t') else {
                continue;
            };
            if requested.contains(path) && validate_package_id(name).is_ok() {
                owners
                    .entry(path.to_string())
                    .or_insert_with(|| name.to_string());
            }
        }
        owners
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::Category;

    #[test]
    fn parses_rpm_inventory() {
        let apps = parse_rpm_query(
            "firefox\t128.1-1.el10\t1024\tx86_64\tApplications/Internet\tWeb browser\nlibfoo\t1-2\t0\tx86_64\tSystem Environment/Libraries\tShared library\n",
        );
        assert_eq!(apps.len(), 2);
        assert_eq!(apps[0].source, Source::Dnf);
        assert_eq!(apps[0].id, "dnf:firefox:128.1-1.el10:x86_64");
        assert_eq!(apps[0].installed_size, Some(1024));
        assert_eq!(apps[0].category, Category::CliApplication);
        assert_eq!(apps[1].category, Category::Library);
        assert_eq!(apps[1].installed_size, None);
        assert_eq!(
            DnfProvider.package_argument(&apps[0]).unwrap(),
            "firefox-128.1-1.el10.x86_64"
        );
        assert_eq!(
            DnfProvider.plan_uninstall(&apps[0], false).unwrap(),
            vec!["dnf", "remove", "-y", "firefox-128.1-1.el10.x86_64"]
        );
    }

    #[test]
    fn parses_dnf_remove_transaction() {
        let out = "Dependencies resolved.\n\n Package Architecture Version Repository Size\nRemoving:\n firefox x86_64 128.1-1.el10 @System 10 M\nRemoving dependent packages:\n firefox-langpacks x86_64 128.1-1.el10 @System 2 M\nTransaction Summary\nRemove 2 Packages\nOperation aborted.\n";
        assert_eq!(
            parse_dnf_removal_preview(out),
            vec![
                "firefox-128.1-1.el10.x86_64",
                "firefox-langpacks-128.1-1.el10.x86_64"
            ]
        );
        assert!(preview_contains_package(
            &parse_dnf_removal_preview(out),
            "firefox-128.1-1.el10.x86_64"
        ));
    }
}
