use std::collections::HashMap;
use std::path::PathBuf;

use crate::discovery::{self, DesktopEntry};
use crate::model::{Category, InstalledApplication, Source};
use crate::provider::PackageProvider;

pub struct ManualProvider;

fn manual_dirs() -> Vec<PathBuf> {
    std::env::var_os("HOME")
        .map(|home| vec![PathBuf::from(home).join(".local/share/applications")])
        .unwrap_or_default()
}

pub fn manual_from_entry(entry: DesktopEntry) -> InstalledApplication {
    let executable = entry.exec_binary();
    let mut app = InstalledApplication::new(Source::Manual, &entry.path);
    app.id = format!("manual:{}", entry.path);
    app.name = entry.name;
    app.description = entry.comment;
    app.executable = executable;
    app.icon = entry.icon;
    app.desktop_file = Some(entry.path);
    app.category = Category::DesktopApplication;
    // A launcher does not prove ownership of the executable or its data.
    app.removable = false;
    app
}

impl PackageProvider for ManualProvider {
    fn source(&self) -> Source {
        Source::Manual
    }

    fn available(&self) -> bool {
        true
    }

    fn scan(&self) -> Result<Vec<InstalledApplication>, String> {
        Ok(discovery::scan_dirs(&manual_dirs())
            .into_iter()
            .map(manual_from_entry)
            .collect())
    }

    fn uninstall_argv(&self, package: &str, _clean: bool) -> Vec<String> {
        vec!["gio".into(), "trash".into(), package.into()]
    }

    fn plan_uninstall(
        &self,
        _app: &InstalledApplication,
        _clean: bool,
    ) -> Result<Vec<String>, String> {
        Err("manual launchers are visible, but their underlying ownership is not proven".into())
    }

    fn owners_of(&self, _paths: &[String]) -> HashMap<String, String> {
        HashMap::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::discovery::DesktopEntry;
    use crate::model::{Category, Source};
    use crate::provider::PackageProvider;

    #[test]
    fn manual_launchers_are_inventory_only_until_ownership_is_proven() {
        let app = manual_from_entry(DesktopEntry {
            path: "/home/test/.local/share/applications/editor.desktop".into(),
            name: "Editor".into(),
            exec: Some("editor".into()),
            icon: None,
            categories: vec![],
            comment: None,
            wm_class: None,
            no_display: false,
        });
        assert_eq!(app.source, Source::Manual);
        assert_eq!(app.category, Category::DesktopApplication);
        assert!(!app.removable);
        assert!(ManualProvider.plan_uninstall(&app, false).is_err());
    }
}
