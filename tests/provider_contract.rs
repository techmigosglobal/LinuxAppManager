use lam_core::model::{Category, InstalledApplication, Source};
use lam_core::provider::PackageProvider;
use lam_core::providers::{
    AppImageProvider, AptProvider, DnfProvider, FlatpakProvider, ManualProvider, PacmanProvider,
    SnapProvider,
};
use std::ffi::OsString;
use std::path::PathBuf;

#[cfg(unix)]
use std::os::unix::fs::PermissionsExt;

struct FakeCommands {
    root: PathBuf,
    old_path: Option<OsString>,
}

impl FakeCommands {
    fn new() -> Self {
        let root = std::env::temp_dir().join(format!(
            "linux-app-manager-fake-providers-{}",
            std::process::id()
        ));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).unwrap();
        let fake_bins = [
            (
                "dpkg-query",
                "#!/bin/sh\nif [ \"$1\" = \"-S\" ]; then printf 'editor: /usr/share/applications/editor.desktop\\n'; else printf 'editor\\t1.0\\t10\\tamd64\\tii \\tutils\\tEditor\\n'; fi\n",
            ),
            (
                "apt-get",
                "#!/bin/sh\nprintf 'Remv editor [1.0]\\n'\n",
            ),
            (
                "rpm",
                "#!/bin/sh\nprintf 'editor\\t1.0-1\\t100\\tx86_64\\tApplications/Internet\\tEditor\\n'\n",
            ),
            (
                "dnf",
                "#!/bin/sh\nexit 0\n",
            ),
            (
                "pacman",
                "#!/bin/sh\nprintf 'editor\\t1.0-1\\tx86_64\\t100\\tEditor\\tArch Linux\\n'\n",
            ),
            (
                "flatpak",
                "#!/bin/sh\nif [ \"$2\" = \"--app\" ]; then printf 'org.example.Editor\\torg.example.Editor/x86_64/stable\\tEditor\\t1.0\\t10 MB\\tTest\\tsystem\\n'; else printf 'org.example.Platform\\torg.example.Platform/x86_64/23.08\\tPlatform\\t23.08\\t10 MB\\tTest\\tsystem\\n'; fi\n",
            ),
            (
                "snap",
                "#!/bin/sh\nprintf 'Name Version Rev Tracking Publisher Notes\\neditor 1.0 1 latest/stable Example -\\n'\n",
            ),
        ];
        for (name, contents) in fake_bins {
            let path = root.join(name);
            std::fs::write(&path, contents).unwrap();
            #[cfg(unix)]
            {
                let mut permissions = std::fs::metadata(&path).unwrap().permissions();
                permissions.set_mode(0o755);
                std::fs::set_permissions(&path, permissions).unwrap();
            }
        }
        let old_path = std::env::var_os("PATH");
        std::env::set_var("PATH", &root);
        Self { root, old_path }
    }
}

impl Drop for FakeCommands {
    fn drop(&mut self) {
        if let Some(path) = &self.old_path {
            std::env::set_var("PATH", path);
        } else {
            std::env::remove_var("PATH");
        }
        let _ = std::fs::remove_dir_all(&self.root);
    }
}

fn desktop_app(source: Source, package: &str) -> InstalledApplication {
    let mut app = InstalledApplication::new(source, package);
    app.category = Category::DesktopApplication;
    app
}

#[test]
fn fake_provider_binaries_cover_inventory_and_non_mutating_apt_preview() {
    let _fake = FakeCommands::new();

    assert!(AptProvider.available());
    let apt_apps = AptProvider.scan().unwrap();
    assert_eq!(apt_apps[0].package_name.as_deref(), Some("editor"));
    assert_eq!(
        AptProvider.removal_preview("editor", false).unwrap(),
        vec!["editor"]
    );

    assert!(DnfProvider.available());
    assert_eq!(DnfProvider.scan().unwrap().len(), 1);

    assert!(PacmanProvider.available());
    assert_eq!(PacmanProvider.scan().unwrap().len(), 1);

    assert!(FlatpakProvider.available());
    assert_eq!(FlatpakProvider.scan().unwrap().len(), 2);

    assert!(SnapProvider.available());
    assert_eq!(SnapProvider.scan().unwrap().len(), 1);
}

#[test]
fn provider_contracts_fix_commands_and_authorization_boundaries() {
    let apt = desktop_app(Source::Apt, "editor");
    assert_eq!(
        AptProvider.uninstall_argv_for(&apt, true),
        vec!["apt-get", "purge", "-y", "editor"]
    );
    assert!(AptProvider.requires_elevation());

    let dnf = desktop_app(Source::Dnf, "editor");
    assert_eq!(
        DnfProvider.uninstall_argv_for(&dnf, false),
        vec!["dnf", "remove", "-y", "editor"]
    );
    assert!(DnfProvider.requires_elevation());

    let pacman = desktop_app(Source::Pacman, "editor");
    assert_eq!(
        PacmanProvider.uninstall_argv_for(&pacman, true),
        vec!["pacman", "-Rns", "--noconfirm", "editor"]
    );
    assert!(PacmanProvider.requires_elevation());

    let flatpak = desktop_app(Source::Flatpak, "org.example.Editor");
    assert_eq!(
        FlatpakProvider.uninstall_argv_for(&flatpak, true),
        vec![
            "flatpak",
            "uninstall",
            "--app",
            "-y",
            "--no-related",
            "--delete-data",
            "org.example.Editor"
        ]
    );

    let snap = desktop_app(Source::Snap, "editor");
    assert_eq!(
        SnapProvider.uninstall_argv_for(&snap, true),
        vec!["snap", "remove", "--purge", "editor"]
    );

    let mut protected = desktop_app(Source::Apt, "bash");
    protected.system_protected = true;
    assert!(AptProvider.plan_uninstall(&protected, false).is_err());

    let manual = desktop_app(Source::Manual, "editor.desktop");
    assert!(ManualProvider.plan_uninstall(&manual, false).is_err());

    let appimage = desktop_app(Source::AppImage, "Editor.AppImage");
    assert!(AppImageProvider.plan_uninstall(&appimage, false).is_err());
}
