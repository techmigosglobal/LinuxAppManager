use std::collections::{HashMap, HashSet};

use serde::Serialize;

use crate::discovery::{self, DesktopEntry};
use crate::model::{Category, InstalledApplication, Source};
use crate::provider::PackageProvider;
use crate::providers::{
    AppImageProvider, AptProvider, DnfProvider, FlatpakProvider, ManualProvider, PacmanProvider,
    SnapProvider,
};

pub struct ScanReport {
    pub apps: Vec<InstalledApplication>,
    pub errors: Vec<String>,
    pub providers: Vec<ProviderStatus>,
}

#[derive(Debug, Clone, Serialize, serde::Deserialize)]
pub struct ProviderStatus {
    pub source: Source,
    pub available: bool,
    pub healthy: bool,
    pub item_count: usize,
    pub message: Option<String>,
}

pub fn all_providers() -> Vec<Box<dyn PackageProvider>> {
    vec![
        Box::new(AptProvider),
        Box::new(DnfProvider),
        Box::new(PacmanProvider),
        Box::new(FlatpakProvider),
        Box::new(SnapProvider),
        Box::new(AppImageProvider),
        Box::new(ManualProvider),
    ]
}

pub fn available_providers() -> Vec<Box<dyn PackageProvider>> {
    all_providers()
        .into_iter()
        .filter(|p| p.available())
        .collect()
}

pub fn scan_all() -> ScanReport {
    let provs = all_providers();
    let (mut apps, mut errors, mut providers) = (vec![], vec![], vec![]);
    let mut healthy_sources = HashSet::new();
    for p in &provs {
        if !p.available() {
            providers.push(ProviderStatus {
                source: p.source(),
                available: false,
                healthy: false,
                item_count: 0,
                message: Some("provider executable was not detected".into()),
            });
            continue;
        }
        match p.scan() {
            Ok(mut a) => {
                let item_count = a.len();
                healthy_sources.insert(p.source());
                providers.push(ProviderStatus {
                    source: p.source(),
                    available: true,
                    healthy: true,
                    item_count,
                    message: None,
                });
                apps.append(&mut a);
            }
            Err(e) => {
                let message = format!("{}: {e}", p.source());
                errors.push(message.clone());
                providers.push(ProviderStatus {
                    source: p.source(),
                    available: true,
                    healthy: false,
                    item_count: 0,
                    message: Some(message),
                });
            }
        }
    }
    let entries = discovery::scan_dirs(&discovery::default_dirs());
    let paths: Vec<String> = entries.iter().map(|e| e.path.clone()).collect();
    let mut owners: HashMap<String, (Source, String)> = HashMap::new();
    for p in &provs {
        if !healthy_sources.contains(&p.source()) {
            continue;
        }
        for (path, pkg) in p.owners_of(&paths) {
            owners.entry(path).or_insert((p.source(), pkg));
        }
    }
    // A user launcher is only considered manual after package providers fail to
    // claim its desktop file. This prevents duplicate APT/Flatpak/Snap entries.
    apps.retain(|app| {
        app.source != Source::Manual
            || app
                .desktop_file
                .as_ref()
                .is_none_or(|path| !owners.contains_key(path))
    });
    link_desktop_entries(&mut apps, &entries, &owners);
    apps.sort_by_key(|a| a.name.to_lowercase());
    ScanReport {
        apps,
        errors,
        providers,
    }
}

/// Correlates packages with user-facing .desktop entries (PRD sections 23–24).
pub fn link_desktop_entries(
    apps: &mut [InstalledApplication],
    entries: &[DesktopEntry],
    owners: &HashMap<String, (Source, String)>,
) {
    for e in entries.iter().filter(|e| !e.no_display) {
        let Some((src, pkg)) = owners.get(&e.path) else {
            continue;
        };
        if let Some(a) = apps
            .iter_mut()
            .find(|a| a.source == *src && a.package_name.as_deref() == Some(pkg.as_str()))
        {
            a.category = Category::DesktopApplication;
            a.name = e.name.clone();
            a.desktop_file = Some(e.path.clone());
            a.executable = e.exec_binary();
            a.icon = e.icon.clone();
            if e.comment.is_some() {
                a.description = e.comment.clone();
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::discovery::parse_desktop;

    #[test]
    fn provider_status_can_report_detected_but_unhealthy() {
        let status = ProviderStatus {
            source: Source::Dnf,
            available: true,
            healthy: false,
            item_count: 0,
            message: Some("RPM database is not readable".into()),
        };
        assert!(status.available);
        assert!(!status.healthy);
        assert_eq!(
            status.message.as_deref(),
            Some("RPM database is not readable")
        );
    }

    #[test]
    fn links_entry_to_package() {
        let mut apps = vec![InstalledApplication::new(Source::Apt, "firefox")];
        let e = parse_desktop(
            "/usr/share/applications/firefox.desktop",
            "[Desktop Entry]\nType=Application\nName=Firefox\nExec=firefox %u\n",
        )
        .unwrap();
        let mut o = HashMap::new();
        o.insert(e.path.clone(), (Source::Apt, "firefox".to_string()));
        link_desktop_entries(&mut apps, &[e], &o);
        assert_eq!(apps[0].category, Category::DesktopApplication);
        assert_eq!(apps[0].name, "Firefox");
    }
}
