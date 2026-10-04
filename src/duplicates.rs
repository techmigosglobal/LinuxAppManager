//! Duplicate-install detection (PRD section 25). Groups by normalized display name.
use crate::model::InstalledApplication;
use std::collections::{BTreeMap, HashSet};

fn key(name: &str) -> String {
    name.chars()
        .filter(|c| c.is_alphanumeric())
        .flat_map(char::to_lowercase)
        .collect()
}

pub fn find_duplicates(apps: &[InstalledApplication]) -> Vec<Vec<InstalledApplication>> {
    let mut g: BTreeMap<String, Vec<InstalledApplication>> = BTreeMap::new();
    for a in apps.iter().filter(|a| a.is_user_facing()) {
        g.entry(key(&a.name)).or_default().push(a.clone());
    }
    g.into_values()
        .filter(|v| v.iter().map(|a| a.source).collect::<HashSet<_>>().len() > 1)
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::{Category, Source};
    fn app(s: Source, n: &str) -> InstalledApplication {
        let mut a = InstalledApplication::new(s, n);
        a.name = n.into();
        a.category = Category::DesktopApplication;
        a
    }
    #[test]
    fn finds_cross_source() {
        let apps = vec![
            app(Source::Apt, "Firefox"),
            app(Source::Snap, "firefox"),
            app(Source::Flatpak, "Firefox"),
            app(Source::Apt, "VLC"),
        ];
        let d = find_duplicates(&apps);
        assert_eq!(d.len(), 1);
        assert_eq!(d[0].len(), 3);
    }
}
