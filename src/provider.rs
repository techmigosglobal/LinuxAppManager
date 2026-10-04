use std::collections::HashMap;
use std::process::Command;

use crate::model::{InstalledApplication, Source};
use crate::security::{is_protected, validate_package_id};

#[derive(Debug, Clone)]
pub struct UninstallPlan {
    pub argv: Vec<String>,
    pub affected_packages: Vec<String>,
    pub requires_elevation: bool,
}

/// Adapter for one installation mechanism (PRD sections 8 and 53).
/// There is deliberately no generic `run_command` API: providers can only
/// build the fixed argument vectors they define.
pub trait PackageProvider {
    fn source(&self) -> Source;
    fn available(&self) -> bool;
    fn scan(&self) -> Result<Vec<InstalledApplication>, String>;
    fn package_argument(&self, app: &InstalledApplication) -> Result<String, String> {
        app.package_name
            .clone()
            .ok_or_else(|| "this item has no package name".into())
    }
    /// Fixed argv (program first) for a removal; `clean` also purges app config/data.
    fn uninstall_argv(&self, package: &str, clean: bool) -> Vec<String>;
    fn uninstall_argv_for(&self, app: &InstalledApplication, clean: bool) -> Vec<String> {
        self.uninstall_argv(app.package_name.as_deref().unwrap_or(""), clean)
    }
    fn requires_elevation(&self) -> bool {
        false
    }
    /// Packages in the package manager's dry-run removal transaction.
    fn removal_preview(&self, _package: &str, _clean: bool) -> Result<Vec<String>, String> {
        Ok(Vec::new())
    }
    /// Maps absolute file paths (e.g. .desktop files) to the package that owns them.
    fn owners_of(&self, _paths: &[String]) -> HashMap<String, String> {
        HashMap::new()
    }

    /// Validates and returns the fixed provider command. This method never executes it.
    fn plan_uninstall(
        &self,
        app: &InstalledApplication,
        clean: bool,
    ) -> Result<Vec<String>, String> {
        if app.system_protected {
            return Err(format!(
                "{} is a protected system package and cannot be removed",
                app.name
            ));
        }
        let pkg = self.package_argument(app)?;
        validate_package_id(&pkg)?;
        if is_protected(&pkg) {
            return Err(format!(
                "{} is a protected system package and cannot be removed",
                app.name
            ));
        }
        if !app.removable {
            return Err(format!(
                "{} is marked as non-removable for safety",
                app.name
            ));
        }
        Ok(self.uninstall_argv_for(app, clean))
    }

    /// Rechecks the item and dependency transaction immediately before showing or executing it.
    fn prepare_uninstall(
        &self,
        app: &InstalledApplication,
        clean: bool,
    ) -> Result<UninstallPlan, String> {
        let argv = self.plan_uninstall(app, clean)?;
        let package = self.package_argument(app)?;
        let affected_packages = self.removal_preview(&package, clean)?;
        let protected: Vec<&str> = affected_packages
            .iter()
            .map(String::as_str)
            .filter(|p| is_protected(p))
            .collect();
        if !protected.is_empty() {
            return Err(format!(
                "the package manager would also remove protected system packages: {}",
                protected.join(", ")
            ));
        }
        Ok(UninstallPlan {
            argv,
            affected_packages,
            requires_elevation: self.requires_elevation(),
        })
    }
}

pub fn which(bin: &str) -> bool {
    std::env::var_os("PATH")
        .map(|p| std::env::split_paths(&p).any(|d| d.join(bin).is_file()))
        .unwrap_or(false)
}

/// Runs a program directly (never through a shell). Returns stdout; fails only if the
/// program can't start, or exits non-zero with no output.
pub fn run(program: &str, args: &[&str]) -> Result<String, String> {
    let out = Command::new(program)
        .args(args)
        .env("LC_ALL", "C")
        .output()
        .map_err(|e| format!("could not run {program}: {e}"))?;
    let stdout = String::from_utf8_lossy(&out.stdout).into_owned();
    if !out.status.success() && stdout.trim().is_empty() {
        return Err(format!(
            "{program} failed: {}",
            String::from_utf8_lossy(&out.stderr).trim()
        ));
    }
    Ok(stdout)
}
