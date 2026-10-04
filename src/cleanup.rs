use std::path::{Path, PathBuf};

use serde::Serialize;

use crate::model::{InstalledApplication, Source};
use crate::util::dir_size;

#[derive(Debug, Clone, Serialize)]
pub struct CleanupCandidate {
    pub kind: String,
    pub label: String,
    pub path: String,
    pub bytes: u64,
    pub removable: bool,
    pub reason: String,
}

/// Builds the only cleanup command currently supported by the application.
///
/// The command is deliberately a recoverable Trash operation. Re-canonicalizing
/// the path at execution time closes the inspect/execute symlink replacement
/// window and keeps cleanup inside the current user's home directory.
pub fn plan(candidate: &CleanupCandidate) -> Result<Vec<String>, String> {
    if !candidate.removable {
        return Err(format!(
            "{} is not removable automatically",
            candidate.label
        ));
    }
    if candidate.kind != "application_data" {
        return Err(format!(
            "cleanup kind {:?} is not supported",
            candidate.kind
        ));
    }
    let home = home_dir().ok_or("HOME is not set; refusing cleanup")?;
    let home = home
        .canonicalize()
        .map_err(|error| format!("cannot resolve home directory: {error}"))?;
    let path = PathBuf::from(&candidate.path)
        .canonicalize()
        .map_err(|error| format!("cannot resolve cleanup path: {error}"))?;
    if !is_under(&path, &home) || path == home {
        return Err("cleanup path is outside the current user's home".into());
    }
    if !path.is_dir() {
        return Err("cleanup target is no longer a directory".into());
    }
    Ok(vec![
        "gio".into(),
        "trash".into(),
        path.to_string_lossy().into_owned(),
    ])
}

fn home_dir() -> Option<PathBuf> {
    std::env::var_os("HOME").map(PathBuf::from)
}

fn is_under(path: &Path, root: &Path) -> bool {
    path == root || path.starts_with(root)
}

fn candidate(
    kind: &str,
    label: &str,
    path: PathBuf,
    home: &Path,
    removable: bool,
    reason: &str,
) -> Option<CleanupCandidate> {
    let canonical = path.canonicalize().ok()?;
    if !is_under(&canonical, home) {
        return None;
    }
    Some(CleanupCandidate {
        kind: kind.into(),
        label: label.into(),
        path: canonical.to_string_lossy().into_owned(),
        bytes: dir_size(&canonical),
        removable,
        reason: reason.into(),
    })
}

/// Returns only known, user-owned paths. This function never deletes anything.
pub fn inspect(app: &InstalledApplication) -> Vec<CleanupCandidate> {
    let Some(home) = home_dir() else {
        return Vec::new();
    };
    let Some(package) = app.package_name.as_deref() else {
        return Vec::new();
    };
    match app.source {
        Source::Flatpak if app.installation.as_deref() == Some("user") => candidate(
            "application_data",
            "Flatpak user data",
            home.join(".var/app").join(package),
            &home,
            true,
            "Flatpak --delete-data can remove this provider-owned user directory.",
        )
        .into_iter()
        .collect(),
        Source::Snap => candidate(
            "application_data",
            "Snap user data",
            home.join("snap").join(package),
            &home,
            false,
            "Snap data is provider-managed; use the reviewed Snap purge operation.",
        )
        .into_iter()
        .collect(),
        Source::Manual => app
            .desktop_file
            .as_ref()
            .and_then(|path| {
                candidate(
                    "launcher",
                    "Manual desktop launcher",
                    PathBuf::from(path),
                    &home,
                    false,
                    "A launcher does not prove ownership of the underlying executable or data.",
                )
            })
            .into_iter()
            .collect(),
        _ => Vec::new(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::Source;

    #[test]
    fn unknown_sources_have_no_destructive_cleanup_guess() {
        let app = InstalledApplication::new(Source::Apt, "firefox");
        assert!(inspect(&app).is_empty());
    }

    #[test]
    fn paths_outside_home_are_not_candidates() {
        assert!(!is_under(Path::new("/opt/app"), Path::new("/home/test")));
    }

    #[test]
    fn cleanup_plan_rejects_outside_and_non_removable_targets() {
        let path =
            std::env::temp_dir().join(format!("linux-app-manager-cleanup-{}", std::process::id()));
        std::fs::create_dir_all(&path).unwrap();
        let removable = CleanupCandidate {
            kind: "application_data".into(),
            label: "Flatpak user data".into(),
            path: path.to_string_lossy().into_owned(),
            bytes: 0,
            removable: true,
            reason: "test".into(),
        };
        assert!(plan(&removable).is_err());
        let protected = CleanupCandidate {
            removable: false,
            ..removable
        };
        assert!(plan(&protected).is_err());
        let _ = std::fs::remove_dir(&path);
    }
}
