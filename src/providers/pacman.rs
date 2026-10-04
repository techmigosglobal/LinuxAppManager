//! Pacman inventory and guarded removal support.

use std::collections::HashMap;
use std::path::Path;

use crate::model::{InstalledApplication, Source};
use crate::provider::{run, which, PackageProvider};
use crate::security::{is_protected, validate_package_id};

pub struct PacmanProvider;

const FORMAT: &str = "%n\t%v\t%a\t%s\t%d\t%p";

pub fn parse_pacman_query(out: &str) -> Vec<InstalledApplication> {
    out.lines()
        .filter_map(|line| {
            let fields: Vec<&str> = line.split('\t').collect();
            if fields.len() < 6 || fields[0].is_empty() || validate_package_id(fields[0]).is_err() {
                return None;
            }
            let mut app = InstalledApplication::new(Source::Pacman, fields[0]);
            app.version = Some(fields[1].to_string()).filter(|v| !v.is_empty());
            app.architecture = Some(fields[2].to_string()).filter(|v| !v.is_empty());
            app.installed_size = fields[3].parse::<u64>().ok();
            app.description = Some(fields[4].to_string()).filter(|v| !v.is_empty());
            app.publisher = Some(fields[5].to_string()).filter(|v| !v.is_empty());
            app.system_protected = is_protected(fields[0]);
            app.removable = !app.system_protected;
            Some(app)
        })
        .collect()
}

pub fn parse_pacman_removal_preview(out: &str) -> Vec<String> {
    let mut seen = std::collections::HashSet::new();
    out.lines()
        .map(str::trim)
        .filter(|line| !line.is_empty())
        .filter(|line| validate_package_id(line).is_ok())
        .filter_map(|line| {
            if seen.insert(line.to_string()) {
                Some(line.to_string())
            } else {
                None
            }
        })
        .collect()
}

fn preview_contains_package(preview: &[String], package: &str) -> bool {
    preview.iter().any(|item| item == package)
}

fn parse_pacman_owners(out: &str) -> HashMap<String, String> {
    out.lines()
        .filter_map(|line| {
            let (path, owner) = line.split_once(" is owned by ")?;
            let package = owner.split_whitespace().next()?;
            if Path::new(path).is_absolute() && validate_package_id(package).is_ok() {
                Some((path.to_string(), package.to_string()))
            } else {
                None
            }
        })
        .collect()
}

impl PackageProvider for PacmanProvider {
    fn source(&self) -> Source {
        Source::Pacman
    }

    fn available(&self) -> bool {
        which("pacman")
    }

    fn scan(&self) -> Result<Vec<InstalledApplication>, String> {
        Ok(parse_pacman_query(&run(
            "pacman",
            &["-Q", "--print-format", FORMAT],
        )?))
    }

    fn uninstall_argv(&self, package: &str, clean: bool) -> Vec<String> {
        vec![
            "pacman".into(),
            if clean { "-Rns" } else { "-R" }.into(),
            "--noconfirm".into(),
            package.into(),
        ]
    }

    fn requires_elevation(&self) -> bool {
        true
    }

    fn removal_preview(&self, package: &str, _clean: bool) -> Result<Vec<String>, String> {
        validate_package_id(package)?;
        if !Path::new("/usr/bin/pkexec").is_file() {
            return Err("pkexec is required for a Pacman transaction preview".into());
        }
        let output = run(
            "/usr/bin/pkexec",
            &[
                "/usr/bin/pacman",
                "-R",
                "--print",
                "--print-format",
                "%n",
                package,
            ],
        )?;
        let preview = parse_pacman_removal_preview(&output);
        if preview.is_empty() || !preview_contains_package(&preview, package) {
            return Err("Pacman did not return a complete non-mutating removal preview".into());
        }
        Ok(preview)
    }

    fn owners_of(&self, paths: &[String]) -> HashMap<String, String> {
        if paths.is_empty() {
            return HashMap::new();
        }
        let mut args = vec!["-Qo"];
        args.extend(paths.iter().map(String::as_str));
        run("pacman", &args)
            .map(|output| parse_pacman_owners(&output))
            .unwrap_or_default()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{Category, InstalledApplication, Source};
    use crate::provider::PackageProvider;

    #[test]
    fn parses_pacman_inventory() {
        let apps = parse_pacman_query(
            "firefox\t128.0-1\tx86_64\t250000000\tWeb browser\tArch Linux\nlibfoo\t1-2\tx86_64\t1000\tLibrary\tArch Linux\n",
        );
        assert_eq!(apps.len(), 2);
        assert_eq!(apps[0].source, Source::Pacman);
        assert_eq!(apps[0].version.as_deref(), Some("128.0-1"));
        assert_eq!(apps[0].installed_size, Some(250_000_000));
        assert_eq!(apps[0].category, Category::Unknown);
    }

    #[test]
    fn parses_printed_removal_targets() {
        assert_eq!(
            parse_pacman_removal_preview("firefox\nfirefox-dependencies\n"),
            vec!["firefox", "firefox-dependencies"]
        );
    }

    #[test]
    fn builds_fixed_commands_and_requires_authorization() {
        let mut app = InstalledApplication::new(Source::Pacman, "firefox");
        app.version = Some("128.0-1".into());
        app.architecture = Some("x86_64".into());
        app.category = Category::DesktopApplication;
        assert_eq!(
            PacmanProvider.uninstall_argv_for(&app, true),
            vec!["pacman", "-Rns", "--noconfirm", "firefox"]
        );
        assert!(PacmanProvider.requires_elevation());
    }
}
