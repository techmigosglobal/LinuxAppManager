//! .desktop file discovery (PRD section 24).
use std::collections::HashMap;
use std::path::PathBuf;

#[derive(Debug, Clone)]
pub struct DesktopEntry {
    pub path: String,
    pub name: String,
    pub exec: Option<String>,
    pub icon: Option<String>,
    pub categories: Vec<String>,
    pub comment: Option<String>,
    pub wm_class: Option<String>,
    pub no_display: bool,
}

impl DesktopEntry {
    /// First real token of Exec= (skips `env VAR=x` and %-field codes).
    pub fn exec_binary(&self) -> Option<String> {
        self.exec
            .as_ref()?
            .split_whitespace()
            .find(|t| *t != "env" && !t.contains('=') && !t.starts_with('%'))
            .map(|t| t.trim_matches('"').to_string())
    }
}

pub fn parse_desktop(path: &str, content: &str) -> Option<DesktopEntry> {
    let mut in_entry = false;
    let mut m: HashMap<&str, &str> = HashMap::new();
    for line in content.lines().map(str::trim) {
        if line.starts_with('[') {
            in_entry = line == "[Desktop Entry]";
            continue;
        }
        if !in_entry || line.is_empty() || line.starts_with('#') {
            continue;
        }
        if let Some((k, v)) = line.split_once('=') {
            if !k.contains('[') {
                m.entry(k.trim()).or_insert(v.trim());
            }
        }
    }
    if m.get("Type") != Some(&"Application") {
        return None;
    }
    let s = |k: &str| m.get(k).map(|v| v.to_string());
    Some(DesktopEntry {
        path: path.to_string(),
        name: s("Name")?,
        exec: s("Exec"),
        icon: s("Icon"),
        comment: s("Comment"),
        wm_class: s("StartupWMClass"),
        categories: m
            .get("Categories")
            .map(|c| {
                c.split(';')
                    .filter(|x| !x.is_empty())
                    .map(String::from)
                    .collect()
            })
            .unwrap_or_default(),
        no_display: m.get("NoDisplay") == Some(&"true") || m.get("Hidden") == Some(&"true"),
    })
}

pub fn default_dirs() -> Vec<PathBuf> {
    let mut d: Vec<PathBuf> = [
        "/usr/share/applications",
        "/usr/local/share/applications",
        "/var/lib/flatpak/exports/share/applications",
        "/var/lib/snapd/desktop/applications",
    ]
    .iter()
    .map(PathBuf::from)
    .collect();
    if let Some(h) = std::env::var_os("HOME").map(PathBuf::from) {
        d.push(h.join(".local/share/applications"));
        d.push(h.join(".local/share/flatpak/exports/share/applications"));
    }
    d
}

pub fn scan_dirs(dirs: &[PathBuf]) -> Vec<DesktopEntry> {
    let mut out = vec![];
    for dir in dirs {
        let Ok(rd) = std::fs::read_dir(dir) else {
            continue;
        };
        for e in rd.flatten() {
            let p = e.path();
            if p.extension().is_some_and(|x| x == "desktop") {
                if let Ok(c) = std::fs::read_to_string(&p) {
                    if let Some(d) = parse_desktop(&p.to_string_lossy(), &c) {
                        out.push(d);
                    }
                }
            }
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn parses_entry() {
        let c = "[Desktop Entry]\nType=Application\nName=Firefox\nName[de]=Feuerfuchs\nExec=env MOZ=1 firefox %u\nIcon=firefox\nCategories=Network;WebBrowser;\n[Desktop Action x]\nName=New Window\n";
        let d = parse_desktop("/x/firefox.desktop", c).unwrap();
        assert_eq!(d.name, "Firefox");
        assert_eq!(d.exec_binary().as_deref(), Some("firefox"));
        assert_eq!(d.categories, vec!["Network", "WebBrowser"]);
        assert!(parse_desktop("/x", "[Desktop Entry]\nType=Link\nName=x").is_none());
    }
}
