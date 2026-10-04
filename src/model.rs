use serde::{Deserialize, Serialize};
use std::fmt;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Source {
    Apt,
    Dnf,
    Pacman,
    Snap,
    Flatpak,
    AppImage,
    Pip,
    Npm,
    Cargo,
    Manual,
    Unknown,
}

impl Source {
    pub fn label(&self) -> &'static str {
        match self {
            Source::Apt => "APT",
            Source::Dnf => "DNF",
            Source::Pacman => "PACMAN",
            Source::Snap => "SNAP",
            Source::Flatpak => "FLATPAK",
            Source::AppImage => "APPIMAGE",
            Source::Pip => "PIP",
            Source::Npm => "NPM",
            Source::Cargo => "CARGO",
            Source::Manual => "MANUAL",
            Source::Unknown => "UNKNOWN",
        }
    }
    pub fn parse(s: &str) -> Option<Source> {
        Some(match s.to_ascii_lowercase().as_str() {
            "apt" | "deb" => Source::Apt,
            "dnf" | "rpm" => Source::Dnf,
            "pacman" => Source::Pacman,
            "snap" => Source::Snap,
            "flatpak" => Source::Flatpak,
            "appimage" => Source::AppImage,
            "manual" => Source::Manual,
            _ => return None,
        })
    }
}
impl fmt::Display for Source {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        f.write_str(self.label())
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Category {
    DesktopApplication,
    CliApplication,
    SystemComponent,
    Runtime,
    Library,
    Driver,
    KernelComponent,
    DevelopmentPackage,
    Service,
    LanguagePackage,
    Plugin,
    Unknown,
}
impl Category {
    pub fn label(&self) -> &'static str {
        match self {
            Category::DesktopApplication => "Desktop Application",
            Category::CliApplication => "CLI Application",
            Category::SystemComponent => "System Component",
            Category::Runtime => "Runtime",
            Category::Library => "Library",
            Category::Driver => "Driver",
            Category::KernelComponent => "Kernel Component",
            Category::DevelopmentPackage => "Development Package",
            Category::Service => "Service",
            Category::LanguagePackage => "Language Package",
            Category::Plugin => "Plugin",
            Category::Unknown => "Unknown",
        }
    }
}

/// Unified model every provider converts its data into (PRD section 9).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InstalledApplication {
    pub id: String,
    pub name: String,
    pub version: Option<String>,
    pub description: Option<String>,
    pub publisher: Option<String>,
    pub source: Source,
    /// Package-manager installation scope (for example Flatpak user/system installation).
    pub installation: Option<String>,
    pub package_name: Option<String>,
    /// Exact package-manager reference where one name can have multiple installed builds.
    pub package_ref: Option<String>,
    pub architecture: Option<String>,
    pub executable: Option<String>,
    pub icon: Option<String>,
    pub desktop_file: Option<String>,
    pub installed_size: Option<u64>,
    pub category: Category,
    pub dependencies: Vec<String>,
    pub removable: bool,
    pub system_protected: bool,
}

impl InstalledApplication {
    pub fn new(source: Source, package: &str) -> Self {
        Self {
            id: format!("{}:{}", source.label().to_lowercase(), package),
            name: package.to_string(),
            version: None,
            description: None,
            publisher: None,
            source,
            installation: None,
            package_name: Some(package.to_string()),
            package_ref: None,
            architecture: None,
            executable: None,
            icon: None,
            desktop_file: None,
            installed_size: None,
            category: Category::Unknown,
            dependencies: vec![],
            removable: true,
            system_protected: false,
        }
    }
    /// Shown on the default "Applications" screen (advanced mode shows everything).
    pub fn is_user_facing(&self) -> bool {
        matches!(
            self.category,
            Category::DesktopApplication | Category::CliApplication
        )
    }

    /// Items shown in the default Applications view.
    pub fn is_desktop_application(&self) -> bool {
        self.category == Category::DesktopApplication
    }

    #[cfg(test)]
    fn desktop_app(source: Source) -> Self {
        let mut app = Self::new(source, "example");
        app.category = Category::DesktopApplication;
        app
    }

    #[cfg(test)]
    fn cli_app(source: Source) -> Self {
        let mut app = Self::new(source, "example-cli");
        app.category = Category::CliApplication;
        app
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn distinguishes_default_desktop_apps_from_cli_tools() {
        assert!(InstalledApplication::desktop_app(Source::Apt).is_desktop_application());
        assert!(!InstalledApplication::cli_app(Source::Apt).is_desktop_application());
    }
}
