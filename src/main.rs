use lam_core::cleanup::inspect as inspect_cleanup;
use lam_core::duplicates::find_duplicates;
use lam_core::history::{OperationInput, StateStore};
use lam_core::model::{InstalledApplication, Source};
use lam_core::provider::PackageProvider;
use lam_core::providers::{
    AppImageProvider, AptProvider, DnfProvider, FlatpakProvider, ManualProvider, PacmanProvider,
    SnapProvider,
};
use lam_core::scanner::{scan_all, ScanReport};
use lam_core::security::host_mutations_allowed;
use lam_core::util::human_size;
use serde_json::json;
use std::process::Command;

const HELP: &str = "lam — Linux App Manager (core CLI)

USAGE:
  lam providers [--json]              show provider availability and scan health
  lam list [--all] [--source SRC]     installed applications (--all: every package)
  lam search QUERY                    search name, package, publisher, executable
  lam info NAME                       details for one application
  lam duplicates                      apps installed through more than one source
  lam history [--limit N]             completed package operations
  lam cache                           read the last persisted inventory cache
  lam cleanup NAME [--yes]            inspect or trash known user-owned leftovers
  lam plan-remove NAME [--clean]      preview a removal
  lam uninstall ID --yes [--clean]    remove after confirmation (ID from list --all --json)

Add --json to list, duplicates, or plan-remove for structured output.";

fn row(a: &InstalledApplication) {
    use std::io::Write;
    let r = writeln!(
        std::io::stdout(),
        "{:<30.30} {:<8} {:<14.14} {:>10}  {}",
        a.name,
        a.source,
        a.version.as_deref().unwrap_or("-"),
        a.installed_size.map(human_size).unwrap_or("-".into()),
        a.category.label()
    );
    if r.is_err() {
        std::process::exit(0);
    } // e.g. piped into `head`
}

fn find<'a>(apps: &'a [InstalledApplication], q: &str) -> Vec<&'a InstalledApplication> {
    let q = q.to_lowercase();
    apps.iter()
        .filter(|a| {
            a.id.to_lowercase() == q
                || a.name.to_lowercase() == q
                || a.package_name.as_deref().map(str::to_lowercase).as_deref() == Some(&q)
        })
        .collect()
}

fn should_list(app: &InstalledApplication, all: bool, source: Option<Source>) -> bool {
    (all || app.is_desktop_application()) && source.is_none_or(|s| app.source == s)
}

fn persist_scan(report: &ScanReport) -> Option<String> {
    let store = match StateStore::open_default() {
        Ok(store) => store,
        Err(error) => return Some(error),
    };
    store.record_scan(&report.apps, &report.providers).err()
}

fn persist_operation(
    action: &str,
    app: &InstalledApplication,
    clean: bool,
    status: &str,
    exit_code: Option<i32>,
) {
    let result = StateStore::open_default().and_then(|store| {
        store.record_operation(OperationInput {
            action,
            app_id: &app.id,
            app_name: &app.name,
            source: &app.source.to_string(),
            clean,
            status,
            exit_code,
            output: None,
        })
    });
    if let Err(error) = result {
        eprintln!("warning: could not write operation history: {error}");
    }
}

fn provider_for(s: Source) -> Option<Box<dyn PackageProvider>> {
    match s {
        Source::Apt => Some(Box::new(AptProvider)),
        Source::Dnf => Some(Box::new(DnfProvider)),
        Source::Pacman => Some(Box::new(PacmanProvider)),
        Source::Flatpak => Some(Box::new(FlatpakProvider)),
        Source::Snap => Some(Box::new(SnapProvider)),
        Source::AppImage => Some(Box::new(AppImageProvider)),
        Source::Manual => Some(Box::new(ManualProvider)),
        _ => None,
    }
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let flag = |f: &str| args.iter().any(|a| a == f);
    let positional: Vec<&String> = args
        .iter()
        .skip(1)
        .filter(|a| !a.starts_with("--"))
        .collect();
    match args.first().map(String::as_str) {
        Some("providers") => {
            let report = scan_all();
            if flag("--json") {
                println!("{}", json!(report.providers));
                return;
            }
            for provider in report.providers {
                let marker = if !provider.available {
                    "–"
                } else if provider.healthy {
                    "✓"
                } else {
                    "⚠"
                };
                println!(
                    "{marker} {:<10} {}{}",
                    provider.source,
                    if provider.healthy {
                        "healthy"
                    } else {
                        "unhealthy"
                    },
                    provider
                        .message
                        .map(|message| format!(": {message}"))
                        .unwrap_or_default()
                );
            }
        }
        Some("list") => {
            let rep = scan_all();
            let state_warning = persist_scan(&rep);
            let src = args
                .iter()
                .position(|a| a == "--source")
                .and_then(|i| args.get(i + 1))
                .and_then(|s| Source::parse(s));
            let v: Vec<_> = rep
                .apps
                .iter()
                .filter(|a| should_list(a, flag("--all"), src))
                .collect();
            if flag("--json") {
                println!(
                    "{}",
                    json!({
                        "apps": v,
                        "errors": rep.errors,
                        "providers": rep.providers,
                        "state_warning": state_warning,
                        "duplicates": find_duplicates(&rep.apps)
                    })
                );
                return;
            }
            v.iter().for_each(|a| row(a));
            println!(
                "\n{} shown{}",
                v.len(),
                if flag("--all") {
                    ""
                } else {
                    " (use --all for libraries and system packages)"
                }
            );
            rep.errors.iter().for_each(|e| eprintln!("warning: {e}"));
            if let Some(warning) = state_warning {
                eprintln!("warning: state: {warning}");
            }
        }
        Some("history") => {
            let limit = args
                .iter()
                .position(|arg| arg == "--limit")
                .and_then(|index| args.get(index + 1))
                .and_then(|value| value.parse::<usize>().ok())
                .unwrap_or(50);
            let history = match StateStore::open_default().and_then(|store| store.history(limit)) {
                Ok(history) => history,
                Err(error) => {
                    eprintln!("Could not read operation history: {error}");
                    std::process::exit(1);
                }
            };
            if flag("--json") {
                println!("{}", json!(history));
                return;
            }
            if history.is_empty() {
                println!("No package operations recorded.");
            }
            for item in history {
                println!(
                    "{} {} {} [{}]{}",
                    item.source,
                    item.action,
                    item.app_name,
                    item.status,
                    item.exit_code
                        .map(|code| format!(" exit={code}"))
                        .unwrap_or_default()
                );
            }
        }
        Some("cache") => {
            let cache = match StateStore::open_default().and_then(|store| store.latest_scan()) {
                Ok(cache) => cache,
                Err(error) => {
                    eprintln!("Could not read inventory cache: {error}");
                    std::process::exit(1);
                }
            };
            let Some(cache) = cache else {
                println!("No persisted inventory cache.");
                return;
            };
            if flag("--json") {
                println!("{}", json!(cache));
                return;
            }
            println!(
                "Cache timestamp: {}\n{} applications/packages from {} provider records.",
                cache.scanned_at,
                cache.apps.len(),
                cache.providers.len()
            );
        }
        Some("cleanup") => {
            let rep = scan_all();
            let name = positional.first().map(|value| value.as_str()).unwrap_or("");
            let Some(app) = find(&rep.apps, name).first().copied() else {
                eprintln!("No application found for cleanup inspection.");
                std::process::exit(1);
            };
            let candidates = inspect_cleanup(app);
            if flag("--yes") {
                if !host_mutations_allowed() {
                    eprintln!("Cleanup is disabled in sandboxed builds; install the native package for host changes.");
                    std::process::exit(2);
                }
                let plans: Vec<_> = candidates
                    .iter()
                    .filter(|candidate| candidate.removable)
                    .map(lam_core::cleanup::plan)
                    .collect();
                if plans.is_empty() {
                    eprintln!(
                        "No removable, provider-owned leftovers were found for {}.",
                        app.name
                    );
                    std::process::exit(1);
                }
                for plan in plans {
                    let plan = match plan {
                        Ok(plan) => plan,
                        Err(error) => {
                            eprintln!("Cleanup blocked: {error}");
                            std::process::exit(2);
                        }
                    };
                    let Some(program) = plan.first() else {
                        eprintln!("Cleanup returned an empty command.");
                        std::process::exit(2);
                    };
                    let status = match Command::new(program)
                        .args(&plan[1..])
                        .env("LC_ALL", "C")
                        .status()
                    {
                        Ok(status) => status,
                        Err(error) => {
                            persist_operation("cleanup", app, true, "failed_to_start", None);
                            eprintln!("Could not start cleanup: {error}");
                            std::process::exit(1);
                        }
                    };
                    if !status.success() {
                        persist_operation("cleanup", app, true, "failed", status.code());
                        eprintln!(
                            "Cleanup failed with exit status {}.",
                            status.code().unwrap_or(1)
                        );
                        std::process::exit(status.code().unwrap_or(1));
                    }
                }
                persist_operation("cleanup", app, true, "success", Some(0));
                if flag("--json") {
                    println!("{}", json!({"ok": true, "action": "cleanup"}));
                } else {
                    println!("Cleanup completed using the desktop Trash.");
                }
                return;
            }
            if flag("--json") {
                println!("{}", json!(candidates));
                return;
            }
            if candidates.is_empty() {
                println!("No known user-owned leftovers for {}.", app.name);
            }
            for item in candidates {
                println!(
                    "{}: {} bytes at {}\n  {}\n  removable: {}",
                    item.label, item.bytes, item.path, item.reason, item.removable
                );
            }
        }
        Some("search") => {
            let q = positional
                .first()
                .map(|s| s.to_lowercase())
                .unwrap_or_default();
            scan_all()
                .apps
                .iter()
                .filter(|a| {
                    [
                        Some(&a.name),
                        a.package_name.as_ref(),
                        a.publisher.as_ref(),
                        a.executable.as_ref(),
                    ]
                    .into_iter()
                    .flatten()
                    .any(|f| f.to_lowercase().contains(&q))
                })
                .for_each(row);
        }
        Some("info") => {
            let rep = scan_all();
            let hits = find(
                &rep.apps,
                positional.first().map(|s| s.as_str()).unwrap_or(""),
            );
            if hits.is_empty() {
                eprintln!("No application found.");
                std::process::exit(1);
            }
            for a in hits {
                println!("{}\n  Source: {}\n  Package: {}\n  Version: {}\n  Category: {}\n  Size: {}\n  Executable: {}\n  Desktop file: {}\n  Protected: {}\n",
                    a.name, a.source, a.package_name.as_deref().unwrap_or("-"), a.version.as_deref().unwrap_or("-"), a.category.label(),
                    a.installed_size.map(human_size).unwrap_or("-".into()), a.executable.as_deref().unwrap_or("-"),
                    a.desktop_file.as_deref().unwrap_or("-"), if a.system_protected { "yes" } else { "no" });
            }
        }
        Some("duplicates") => {
            let d = find_duplicates(&scan_all().apps);
            if flag("--json") {
                println!("{}", json!(d));
                return;
            }
            if d.is_empty() {
                println!("No duplicate installations found.");
            }
            for g in d {
                println!("{} — {} installations detected", g[0].name, g.len());
                g.iter().for_each(|a| {
                    println!(
                        "   {:<8} {:<12} {}",
                        a.source,
                        a.version.as_deref().unwrap_or("-"),
                        a.installed_size.map(human_size).unwrap_or("-".into())
                    )
                });
            }
        }
        Some("plan-remove") => {
            let rep = scan_all();
            let name = positional.first().map(|s| s.as_str()).unwrap_or("");
            let hits = find(&rep.apps, name);
            let Some(app) = hits.first() else {
                let message = format!("No application named {name:?}.");
                if flag("--json") {
                    println!("{}", json!({"ok": false, "error": message}));
                    return;
                }
                eprintln!("{message}");
                std::process::exit(1)
            };
            let Some(p) = provider_for(app.source) else {
                let message = format!("Removal for {} is not supported yet.", app.source);
                if flag("--json") {
                    println!("{}", json!({"ok": false, "error": message}));
                    return;
                }
                eprintln!("{message}");
                std::process::exit(1)
            };
            match p.prepare_uninstall(app, flag("--clean")) {
                Err(e) => {
                    if flag("--json") {
                        println!("{}", json!({"ok": false, "error": e}));
                        return;
                    }
                    eprintln!("✗ Blocked: {e}");
                    std::process::exit(2)
                }
                Ok(plan) => {
                    if flag("--json") {
                        println!(
                            "{}",
                            json!({
                                "ok": true,
                                "argv": plan.argv,
                                "preview": plan.affected_packages,
                                "requires_elevation": plan.requires_elevation
                            })
                        );
                        return;
                    }
                    println!(
                        "Removal command: {}{}",
                        if plan.requires_elevation {
                            "pkexec "
                        } else {
                            ""
                        },
                        plan.argv.join(" ")
                    );
                    if !plan.affected_packages.is_empty() {
                        println!(
                            "Packages in the removal transaction ({}):",
                            plan.affected_packages.len()
                        );
                        plan.affected_packages
                            .iter()
                            .for_each(|x| println!("   - {x}"));
                    }
                }
            }
        }
        Some("uninstall") => {
            let Some(id) = positional.first().map(|s| s.as_str()) else {
                eprintln!("Provide an application ID from `lam list --all`.");
                std::process::exit(2);
            };
            if !flag("--yes") {
                eprintln!("Uninstall requires explicit confirmation: pass --yes after reviewing `lam plan-remove ID`.");
                std::process::exit(2);
            }
            if !host_mutations_allowed() {
                eprintln!("Host package changes are disabled in sandboxed builds; install the native package for reviewed removal operations.");
                std::process::exit(2);
            }
            println!("Verifying the reviewed package transaction…");
            let report = scan_all();
            let hits: Vec<_> = report.apps.iter().filter(|app| app.id == id).collect();
            let Some(app) = hits.first() else {
                eprintln!("No installed application or package with ID {id:?}.");
                std::process::exit(1);
            };
            let Some(provider) = provider_for(app.source) else {
                eprintln!("Uninstall for {} is not supported yet.", app.source);
                std::process::exit(1);
            };
            let plan = match provider.prepare_uninstall(app, flag("--clean")) {
                Ok(plan) => plan,
                Err(error) => {
                    eprintln!("Removal blocked: {error}");
                    std::process::exit(2);
                }
            };
            if let Some(expected) = args
                .iter()
                .position(|arg| arg == "--expected-preview")
                .and_then(|i| args.get(i + 1))
            {
                let mut expected: Vec<&str> = expected
                    .split(',')
                    .filter(|item| !item.is_empty())
                    .collect();
                let mut actual: Vec<&str> =
                    plan.affected_packages.iter().map(String::as_str).collect();
                expected.sort_unstable();
                actual.sort_unstable();
                if expected != actual {
                    eprintln!("The removal transaction changed since it was reviewed. Build a new plan and confirm again.");
                    std::process::exit(3);
                }
            }
            println!("Starting package transaction for {}.", app.name);
            if !plan.affected_packages.is_empty() {
                println!(
                    "The package manager will remove: {}",
                    plan.affected_packages.join(", ")
                );
            }
            let mut command = if plan.requires_elevation {
                if !std::path::Path::new("/usr/bin/pkexec").is_file() {
                    eprintln!("pkexec is required to authorize this package operation.");
                    std::process::exit(1);
                }
                let executable = match app.source {
                    Source::Apt => "/usr/bin/apt-get",
                    Source::Dnf => "/usr/bin/dnf",
                    Source::Pacman => "/usr/bin/pacman",
                    _ => {
                        eprintln!("No authorized command is configured for {}.", app.source);
                        std::process::exit(1);
                    }
                };
                let mut cmd = Command::new("/usr/bin/pkexec");
                cmd.arg(executable).args(plan.argv.iter().skip(1));
                cmd
            } else {
                let Some(executable) = plan.argv.first() else {
                    eprintln!("The provider returned an empty uninstall plan.");
                    std::process::exit(1);
                };
                let mut cmd = Command::new(executable);
                cmd.args(plan.argv.iter().skip(1));
                cmd
            };
            let status = match command.env("LC_ALL", "C").status() {
                Ok(status) => status,
                Err(error) => {
                    persist_operation("uninstall", app, flag("--clean"), "failed_to_start", None);
                    eprintln!("Could not start the package transaction: {error}");
                    std::process::exit(1);
                }
            };
            let exit_code = status.code();
            if status.success() {
                persist_operation("uninstall", app, flag("--clean"), "success", exit_code);
                println!("Uninstall completed successfully.");
            } else {
                persist_operation("uninstall", app, flag("--clean"), "failed", exit_code);
                eprintln!(
                    "Uninstall failed with exit status {}.",
                    status.code().unwrap_or(1)
                );
                std::process::exit(status.code().unwrap_or(1));
            }
        }
        _ => println!("{HELP}"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use lam_core::model::Category;

    #[test]
    fn default_list_excludes_cli_tools() {
        let mut cli = InstalledApplication::new(Source::Apt, "ripgrep");
        cli.category = Category::CliApplication;
        let mut desktop = InstalledApplication::new(Source::Apt, "firefox");
        desktop.category = Category::DesktopApplication;

        assert!(!should_list(&cli, false, None));
        assert!(should_list(&desktop, false, None));
        assert!(should_list(&cli, true, None));
    }
}
