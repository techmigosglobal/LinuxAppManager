use std::collections::HashMap;
use std::path::Path;

use crate::model::{Category, InstalledApplication, Source};
use crate::provider::{run, which, PackageProvider};
use crate::util::parse_size;

pub struct FlatpakProvider;

pub fn parse_flatpak_list(out: &str, category: Category) -> Vec<InstalledApplication> {
    out.lines()
        .filter_map(|l| {
            let f: Vec<&str> = l.split('\t').collect();
            if f.len() < 7 || f[0].is_empty() || f[0] == "Application ID" {
                return None;
            }
            let mut a = InstalledApplication::new(Source::Flatpak, f[0]);
            let reference = f[1];
            let installation = f[6].trim().to_string();
            let installation = if installation.is_empty() {
                "unknown".to_string()
            } else {
                installation
            };
            a.installation = Some(installation.to_string());
            a.package_ref = Some(reference.to_string());
            a.id = format!("flatpak:{installation}:{reference}");
            a.name = f[2].to_string();
            a.version = Some(f[3].to_string()).filter(|v| !v.is_empty());
            a.installed_size = parse_size(f[4]);
            a.publisher = Some(f[5].to_string()).filter(|v| !v.is_empty());
            a.category = category;
            if category == Category::Runtime {
                a.removable = false;
            }
            Some(a)
        })
        .collect()
}

impl PackageProvider for FlatpakProvider {
    fn source(&self) -> Source {
        Source::Flatpak
    }
    fn available(&self) -> bool {
        which("flatpak")
    }
    fn scan(&self) -> Result<Vec<InstalledApplication>, String> {
        let columns = "--columns=application,ref,name,version,size,origin,installation";
        let mut apps = parse_flatpak_list(
            &run("flatpak", &["list", "--app", columns])?,
            Category::DesktopApplication,
        );
        apps.extend(parse_flatpak_list(
            &run("flatpak", &["list", "--runtime", columns])?,
            Category::Runtime,
        ));
        Ok(apps)
    }
    fn package_argument(&self, app: &InstalledApplication) -> Result<String, String> {
        if let Some(reference) = app.package_ref.as_deref() {
            let parts: Vec<&str> = reference.split('/').collect();
            if parts.len() != 3
                || parts
                    .iter()
                    .any(|part| crate::security::validate_package_id(part).is_err())
            {
                return Err(format!("invalid Flatpak reference: {reference:?}"));
            }
        }
        app.package_name
            .clone()
            .ok_or_else(|| "this item has no package name".into())
    }
    fn uninstall_argv(&self, package: &str, clean: bool) -> Vec<String> {
        let mut v = vec![
            "flatpak".to_string(),
            "uninstall".into(),
            "-y".into(),
            "--no-related".into(),
        ];
        if clean {
            v.push("--delete-data".into());
        }
        v.push(package.into());
        v
    }
    fn uninstall_argv_for(&self, app: &InstalledApplication, clean: bool) -> Vec<String> {
        let package = app
            .package_ref
            .as_deref()
            .or(app.package_name.as_deref())
            .unwrap_or("");
        let mut argv = self.uninstall_argv(package, clean);
        argv.insert(2, "--app".into());
        if let Some(installation) = app.installation.as_deref() {
            let option = match installation {
                "user" => "--user".to_string(),
                "system" => "--system".to_string(),
                name => format!("--installation={name}"),
            };
            argv.insert(2, option);
        }
        argv
    }
    /// Flatpak exports "<app-id>.desktop" files, so ownership is the file stem.
    fn owners_of(&self, paths: &[String]) -> HashMap<String, String> {
        paths
            .iter()
            .filter(|p| p.contains("/flatpak/exports/"))
            .filter_map(|p| Some((p.clone(), Path::new(p).file_stem()?.to_str()?.to_string())))
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn parses_list() {
        let a = parse_flatpak_list("org.gimp.GIMP\torg.gimp.GIMP/x86_64/stable\tGIMP\t2.10.38\t620.1 MB\tflathub\tsystem\n", Category::DesktopApplication);
        assert_eq!(a[0].name, "GIMP");
        assert_eq!(a[0].installation.as_deref(), Some("system"));
        assert_eq!(a[0].id, "flatpak:system:org.gimp.GIMP/x86_64/stable");
        assert_eq!(a[0].installed_size, Some(620_100_000));
        assert_eq!(a[0].package_name.as_deref(), Some("org.gimp.GIMP"));
        assert_eq!(
            FlatpakProvider.uninstall_argv("org.gimp.GIMP", true),
            vec![
                "flatpak",
                "uninstall",
                "-y",
                "--no-related",
                "--delete-data",
                "org.gimp.GIMP"
            ]
        );
        assert_eq!(
            FlatpakProvider.uninstall_argv_for(&a[0], false),
            vec![
                "flatpak",
                "uninstall",
                "--system",
                "--app",
                "-y",
                "--no-related",
                "org.gimp.GIMP/x86_64/stable"
            ]
        );
        assert_eq!(
            FlatpakProvider.plan_uninstall(&a[0], false).unwrap(),
            vec![
                "flatpak",
                "uninstall",
                "--system",
                "--app",
                "-y",
                "--no-related",
                "org.gimp.GIMP/x86_64/stable"
            ]
        );
    }

    #[test]
    fn lists_flatpak_runtimes_but_blocks_removal() {
        let runtime = parse_flatpak_list(
            "org.gnome.Platform\torg.gnome.Platform/x86_64/48\tGNOME Platform\t\t1.1 GB\tflathub\tsystem\n",
            Category::Runtime,
        ).remove(0);
        assert_eq!(runtime.category, Category::Runtime);
        assert!(!runtime.removable);
        assert!(FlatpakProvider.plan_uninstall(&runtime, false).is_err());
        assert_eq!(
            FlatpakProvider.package_argument(&runtime).unwrap(),
            "org.gnome.Platform"
        );
    }

    #[test]
    fn rejects_malformed_flatpak_reference() {
        let mut app = parse_flatpak_list(
            "org.gimp.GIMP\torg.gimp.GIMP/x86_64/stable\tGIMP\t2.10.38\t620.1 MB\tflathub\tsystem\n",
            Category::DesktopApplication,
        ).remove(0);
        app.package_ref = Some("org.gimp.GIMP/../../bad".into());
        assert!(FlatpakProvider.plan_uninstall(&app, false).is_err());
    }
}
