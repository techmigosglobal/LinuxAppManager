//! Pacman inventory and guarded removal support.

use std::collections::HashMap;
use std::path::Path;

use crate::model::{InstalledApplication, Source};
use crate::provider::{run, which, PackageProvider};
use crate::security::{is_protected, validate_package_id};

pub struct PacmanProvider;

/// `--print-format` is a transaction option and is rejected by `pacman -Q`.
/// Query installed metadata with `-Qi` under LC_ALL=C instead.
const QUERY_ARGS: &[&str] = &["-Qi", "--color", "never"];

fn installed_bytes(value: &str) -> Option<u64> {
    let mut fields = value.split_whitespace();
    let size = fields.next()?.parse::<f64>().ok()?;
    let multiplier = match fields.next()? {
        "B" => 1.0,
        "KiB" => 1024.0,
        "MiB" => 1024.0 * 1024.0,
        "GiB" => 1024.0 * 1024.0 * 1024.0,
        "TiB" => 1024.0 * 1024.0 * 1024.0 * 1024.0,
        _ => return None,
    };
    let bytes = size * multiplier;
    (bytes.is_finite() && bytes >= 0.0 && bytes < u64::MAX as f64).then_some(bytes.round() as u64)
}

pub fn parse_pacman_query(out: &str) -> Vec<InstalledApplication> {
    out.split("\n\n")
        .filter_map(|record| {
            let mut fields = HashMap::<&str, String>::new();
            let mut previous = "";
            for line in record.lines() {
                if line.starts_with(char::is_whitespace) {
                    // Descriptions and packagers can wrap; dependency continuations
                    // must not become part of either field.
                    if matches!(previous, "Description" | "Packager") {
                        if let Some(value) = fields.get_mut(previous) {
                            value.push(' ');
                            value.push_str(line.trim());
                        }
                    }
                    continue;
                }
                if let Some((key, value)) = line.split_once(':') {
                    previous = key.trim();
                    fields.insert(previous, value.trim().to_string());
                }
            }
            let name = fields.get("Name")?;
            if validate_package_id(name).is_err() {
                return None;
            }
            let mut app = InstalledApplication::new(Source::Pacman, name);
            let value = |key| fields.get(key).cloned().filter(|value| !value.is_empty());
            app.version = value("Version");
            app.architecture = value("Architecture");
            app.installed_size = fields
                .get("Installed Size")
                .and_then(|value| installed_bytes(value));
            app.description = value("Description");
            app.publisher = value("Packager");
            app.system_protected = is_protected(name);
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
        Ok(parse_pacman_query(&run("pacman", QUERY_ARGS)?))
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
            "Name            : firefox\nVersion         : 2:128.0-1\nDescription     : Web browser: desktop\n                  with wrapped description\nArchitecture    : x86_64\nInstalled Size  : 250.00 MiB\nPackager        : Arch Linux <packager@example.org>\nOptional Deps   : speech-dispatcher: text-to-speech\n                  hunspell: spell checking\n\nName            : libfoo\nVersion         : 1-2\nDescription     : Library\nArchitecture    : x86_64\nInstalled Size  : 1.00 KiB\nPackager        : Arch Linux\n",
        );
        assert_eq!(apps.len(), 2);
        assert_eq!(apps[0].source, Source::Pacman);
        assert_eq!(apps[0].version.as_deref(), Some("2:128.0-1"));
        assert_eq!(apps[0].installed_size, Some(250 * 1024 * 1024));
        assert_eq!(
            apps[0].description.as_deref(),
            Some("Web browser: desktop with wrapped description")
        );
        assert_eq!(
            apps[0].publisher.as_deref(),
            Some("Arch Linux <packager@example.org>")
        );
        assert_eq!(apps[1].installed_size, Some(1024));
        assert_eq!(apps[0].category, Category::Unknown);
    }

    #[test]
    fn rejects_malformed_inventory_and_preserves_unknown_size() {
        let apps = parse_pacman_query("Name : bad/name\nVersion : 1\n\nName : pacman\nVersion : 7.1.0-1\nInstalled Size : unknown\n\nName : editor\nVersion : 1\nInstalled Size : 1.50 KiB\n");
        assert_eq!(apps.len(), 2);
        assert_eq!(apps[0].installed_size, None);
        assert!(apps[0].system_protected);
        assert!(!apps[0].removable);
        assert_eq!(apps[1].installed_size, Some(1536));
        assert_eq!(installed_bytes("NaN MiB"), None);
        assert_eq!(installed_bytes("-1 MiB"), None);
        assert_eq!(installed_bytes("9e99 GiB"), None);
    }

    #[test]
    fn reads_real_pacman_inventory_from_an_isolated_database_when_available() {
        if !which("pacman") {
            return;
        }
        let unique = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let root = std::env::temp_dir().join(format!("lam-pacman-{}-{unique}", std::process::id()));
        let local = root.join("local");
        let package = local.join("vin-fixture-2:1.2.3-1");
        std::fs::create_dir_all(&package).unwrap();
        std::fs::write(local.join("ALPM_DB_VERSION"), "9\n").unwrap();
        std::fs::write(package.join("desc"), "%NAME%\nvin-fixture\n\n%VERSION%\n2:1.2.3-1\n\n%BASE%\nvin-fixture\n\n%DESC%\nRead only fixture: package inventory\n\n%ARCH%\nx86_64\n\n%SIZE%\n1536\n\n%PACKAGER%\nVIN test <release@example.org>\n\n%LICENSE%\nMIT\n\n").unwrap();
        let output = crate::provider::host_command("pacman")
            .arg("--dbpath")
            .arg(&root)
            .args(QUERY_ARGS)
            .env("LC_ALL", "C")
            .output()
            .unwrap();
        std::fs::remove_dir_all(root).unwrap();
        assert!(
            output.status.success(),
            "{}",
            String::from_utf8_lossy(&output.stderr)
        );
        let apps = parse_pacman_query(&String::from_utf8(output.stdout).unwrap());
        assert_eq!(apps.len(), 1);
        assert_eq!(apps[0].package_name.as_deref(), Some("vin-fixture"));
        assert_eq!(apps[0].version.as_deref(), Some("2:1.2.3-1"));
        assert_eq!(apps[0].installed_size, Some(1536));
        assert_eq!(
            apps[0].description.as_deref(),
            Some("Read only fixture: package inventory")
        );
        assert_eq!(
            apps[0].publisher.as_deref(),
            Some("VIN test <release@example.org>")
        );
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
