use std::path::{Path, PathBuf};

use crate::model::{Category, InstalledApplication, Source};
use crate::provider::PackageProvider;

pub struct AppImageProvider;

fn home_dir() -> Option<PathBuf> {
    std::env::var_os("HOME").map(PathBuf::from)
}

fn is_appimage(path: &Path) -> bool {
    path.extension()
        .and_then(|extension| extension.to_str())
        .is_some_and(|extension| extension.eq_ignore_ascii_case("appimage"))
}

fn is_under(path: &Path, root: &Path) -> bool {
    path == root || path.starts_with(root)
}

fn validate_file_name(name: &str) -> Result<(), String> {
    if name.is_empty()
        || name.len() > 255
        || name == "."
        || name == ".."
        || name.contains('/')
        || name.contains('\\')
        || name.contains('\0')
    {
        return Err(format!("invalid AppImage file name: {name:?}"));
    }
    Ok(())
}

fn appimage_from_path_with_home(path: &Path, home: &Path) -> InstalledApplication {
    let file_name = path
        .file_name()
        .and_then(|name| name.to_str())
        .unwrap_or("AppImage");
    let name = Path::new(file_name)
        .file_stem()
        .and_then(|stem| stem.to_str())
        .unwrap_or(file_name);
    let mut app = InstalledApplication::new(Source::AppImage, file_name);
    app.id = format!("appimage:{}", path.display());
    app.name = name.to_string();
    app.package_ref = Some(path.to_string_lossy().into_owned());
    app.category = Category::DesktopApplication;
    app.removable = is_under(path, home);
    app.installed_size = std::fs::metadata(path).ok().map(|metadata| metadata.len());
    app
}

pub fn appimage_from_path(path: &Path) -> InstalledApplication {
    let home = home_dir().unwrap_or_else(|| PathBuf::from("/"));
    appimage_from_path_with_home(path, &home)
}

fn scan_root(root: &Path, depth: usize, home: &Path, apps: &mut Vec<InstalledApplication>) {
    if depth > 3 {
        return;
    }
    let Ok(entries) = std::fs::read_dir(root) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        let Ok(file_type) = entry.file_type() else {
            continue;
        };
        if file_type.is_symlink() {
            continue;
        }
        if file_type.is_file() && is_appimage(&path) {
            let path = path.canonicalize().unwrap_or(path);
            apps.push(appimage_from_path_with_home(&path, home));
        } else if file_type.is_dir() {
            scan_root(&path, depth + 1, home, apps);
        }
    }
}

impl PackageProvider for AppImageProvider {
    fn source(&self) -> Source {
        Source::AppImage
    }

    fn available(&self) -> bool {
        true
    }

    fn scan(&self) -> Result<Vec<InstalledApplication>, String> {
        let Some(home) = home_dir() else {
            return Ok(Vec::new());
        };
        let roots = [
            home.join("Applications"),
            home.join(".local/bin"),
            PathBuf::from("/opt"),
            PathBuf::from("/usr/local/bin"),
        ];
        let mut apps = Vec::new();
        for root in roots {
            scan_root(&root, 0, &home, &mut apps);
        }
        apps.sort_by(|left, right| left.id.cmp(&right.id));
        apps.dedup_by(|left, right| left.id == right.id);
        Ok(apps)
    }

    fn package_argument(&self, app: &InstalledApplication) -> Result<String, String> {
        let package = app
            .package_name
            .as_deref()
            .ok_or("this AppImage has no file name")?;
        validate_file_name(package)?;
        Ok(package.to_string())
    }

    fn uninstall_argv(&self, package: &str, _clean: bool) -> Vec<String> {
        vec!["gio".into(), "trash".into(), package.into()]
    }

    fn uninstall_argv_for(&self, app: &InstalledApplication, _clean: bool) -> Vec<String> {
        vec![
            "gio".into(),
            "trash".into(),
            app.package_ref.clone().unwrap_or_default(),
        ]
    }

    fn plan_uninstall(
        &self,
        app: &InstalledApplication,
        clean: bool,
    ) -> Result<Vec<String>, String> {
        if !app.removable {
            return Err("system AppImages are visible but cannot be removed automatically".into());
        }
        let Some(path) = app.package_ref.as_deref() else {
            return Err("this AppImage has no file path".into());
        };
        let path = Path::new(path);
        let metadata = std::fs::symlink_metadata(path)
            .map_err(|error| format!("cannot inspect AppImage: {error}"))?;
        if !metadata.is_file() || metadata.file_type().is_symlink() {
            return Err("the AppImage path is not a regular file".into());
        }
        let canonical = path
            .canonicalize()
            .map_err(|error| format!("cannot resolve AppImage path: {error}"))?;
        let Some(home) = home_dir() else {
            return Err("HOME is not set; refusing file removal".into());
        };
        if !is_under(&canonical, &home) {
            return Err("the AppImage is outside the current user's home".into());
        }
        let _ = clean;
        self.package_argument(app)?;
        Ok(self.uninstall_argv_for(app, false))
    }

    fn removal_preview(&self, package: &str, _clean: bool) -> Result<Vec<String>, String> {
        validate_file_name(package)?;
        Ok(vec![package.to_string()])
    }

    fn owners_of(&self, _paths: &[String]) -> std::collections::HashMap<String, String> {
        std::collections::HashMap::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{Category, Source};
    use crate::provider::PackageProvider;

    #[test]
    fn recognizes_appimage_files_and_uses_recoverable_removal() {
        let app = appimage_from_path_with_home(
            Path::new("/home/test/Applications/My Editor.AppImage"),
            Path::new("/home/test"),
        );
        assert_eq!(app.source, Source::AppImage);
        assert_eq!(app.category, Category::DesktopApplication);
        assert_eq!(app.name, "My Editor");
        assert_eq!(app.package_name.as_deref(), Some("My Editor.AppImage"));
        assert!(app.removable);
        assert_eq!(
            AppImageProvider.uninstall_argv_for(&app, false),
            vec!["gio", "trash", "/home/test/Applications/My Editor.AppImage"]
        );
        assert!(AppImageProvider.package_argument(&app).is_ok());
    }

    #[test]
    fn system_appimages_are_visible_but_not_removable() {
        let app = appimage_from_path_with_home(
            Path::new("/opt/Editor.AppImage"),
            Path::new("/home/test"),
        );
        assert!(!app.removable);
        assert!(AppImageProvider.plan_uninstall(&app, false).is_err());
    }
}
