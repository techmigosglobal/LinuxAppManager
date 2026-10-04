use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use rusqlite::{params, Connection, OptionalExtension};
use serde::{Deserialize, Serialize};

use crate::model::InstalledApplication;
use crate::scanner::ProviderStatus;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OperationRecord {
    pub id: i64,
    pub occurred_at: i64,
    pub action: String,
    pub app_id: String,
    pub app_name: String,
    pub source: String,
    pub clean: bool,
    pub status: String,
    pub exit_code: Option<i32>,
    pub output: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CachedScan {
    pub scanned_at: i64,
    pub apps: Vec<InstalledApplication>,
    pub providers: Vec<ProviderStatus>,
}

pub struct OperationInput<'a> {
    pub action: &'a str,
    pub app_id: &'a str,
    pub app_name: &'a str,
    pub source: &'a str,
    pub clean: bool,
    pub status: &'a str,
    pub exit_code: Option<i32>,
    pub output: Option<&'a str>,
}

pub struct StateStore {
    connection: Connection,
}

impl StateStore {
    pub fn open_default() -> Result<Self, String> {
        let path = default_state_path()?;
        Self::open(&path)
    }

    pub fn open(path: &Path) -> Result<Self, String> {
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)
                .map_err(|error| format!("could not create state directory: {error}"))?;
        }
        let connection = Connection::open(path)
            .map_err(|error| format!("could not open state database: {error}"))?;
        connection
            .execute_batch(
                "PRAGMA foreign_keys = ON;
                 CREATE TABLE IF NOT EXISTS scan_cache (
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     scanned_at INTEGER NOT NULL,
                     apps_json TEXT NOT NULL,
                     providers_json TEXT NOT NULL
                 );
                 CREATE TABLE IF NOT EXISTS operation_history (
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     occurred_at INTEGER NOT NULL,
                     action TEXT NOT NULL,
                     app_id TEXT NOT NULL,
                     app_name TEXT NOT NULL,
                     source TEXT NOT NULL,
                     clean INTEGER NOT NULL,
                     status TEXT NOT NULL,
                     exit_code INTEGER,
                     output TEXT
                 );
                 CREATE INDEX IF NOT EXISTS operation_history_occurred_at
                     ON operation_history(occurred_at DESC);",
            )
            .map_err(|error| format!("could not initialize state database: {error}"))?;
        Ok(Self { connection })
    }

    pub fn record_scan(
        &self,
        apps: &[InstalledApplication],
        providers: &[ProviderStatus],
    ) -> Result<(), String> {
        let apps_json = serde_json::to_string(apps)
            .map_err(|error| format!("could not serialize inventory cache: {error}"))?;
        let providers_json = serde_json::to_string(providers)
            .map_err(|error| format!("could not serialize provider cache: {error}"))?;
        self.connection
            .execute(
                "INSERT INTO scan_cache(scanned_at, apps_json, providers_json) VALUES (?1, ?2, ?3)",
                params![unix_now(), apps_json, providers_json],
            )
            .map_err(|error| format!("could not persist inventory cache: {error}"))?;
        self.connection
            .execute(
                "DELETE FROM scan_cache WHERE id NOT IN
                 (SELECT id FROM scan_cache ORDER BY id DESC LIMIT 20)",
                [],
            )
            .map_err(|error| format!("could not prune inventory cache: {error}"))?;
        Ok(())
    }

    pub fn latest_scan(&self) -> Result<Option<CachedScan>, String> {
        let row = self
            .connection
            .query_row(
                "SELECT scanned_at, apps_json, providers_json FROM scan_cache ORDER BY id DESC LIMIT 1",
                [],
                |row| {
                    Ok((
                        row.get::<_, i64>(0)?,
                        row.get::<_, String>(1)?,
                        row.get::<_, String>(2)?,
                    ))
                },
            )
            .optional()
            .map_err(|error| format!("could not read inventory cache: {error}"))?;
        let Some((scanned_at, apps_json, providers_json)) = row else {
            return Ok(None);
        };
        let apps = serde_json::from_str(&apps_json)
            .map_err(|error| format!("could not decode inventory cache: {error}"))?;
        let providers = serde_json::from_str(&providers_json)
            .map_err(|error| format!("could not decode provider cache: {error}"))?;
        Ok(Some(CachedScan {
            scanned_at,
            apps,
            providers,
        }))
    }

    pub fn record_operation(&self, input: OperationInput<'_>) -> Result<(), String> {
        self.connection
            .execute(
                "INSERT INTO operation_history
                 (occurred_at, action, app_id, app_name, source, clean, status, exit_code, output)
                 VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)",
                params![
                    unix_now(),
                    input.action,
                    input.app_id,
                    input.app_name,
                    input.source,
                    input.clean,
                    input.status,
                    input.exit_code,
                    input.output,
                ],
            )
            .map_err(|error| format!("could not persist operation history: {error}"))?;
        Ok(())
    }

    pub fn history(&self, limit: usize) -> Result<Vec<OperationRecord>, String> {
        let mut statement = self
            .connection
            .prepare(
                "SELECT id, occurred_at, action, app_id, app_name, source, clean, status, exit_code, output
                 FROM operation_history ORDER BY occurred_at DESC, id DESC LIMIT ?1",
            )
            .map_err(|error| format!("could not prepare operation history query: {error}"))?;
        let rows = statement
            .query_map(params![limit as i64], |row| {
                Ok(OperationRecord {
                    id: row.get(0)?,
                    occurred_at: row.get(1)?,
                    action: row.get(2)?,
                    app_id: row.get(3)?,
                    app_name: row.get(4)?,
                    source: row.get(5)?,
                    clean: row.get::<_, i64>(6)? != 0,
                    status: row.get(7)?,
                    exit_code: row.get(8)?,
                    output: row.get(9)?,
                })
            })
            .map_err(|error| format!("could not query operation history: {error}"))?;
        rows.collect::<Result<Vec<_>, _>>()
            .map_err(|error| format!("could not read operation history: {error}"))
    }
}

fn default_state_path() -> Result<PathBuf, String> {
    let root = std::env::var_os("XDG_STATE_HOME")
        .map(PathBuf::from)
        .or_else(|| std::env::var_os("HOME").map(|home| PathBuf::from(home).join(".local/state")))
        .ok_or_else(|| "HOME or XDG_STATE_HOME is not set; cannot persist state".to_string())?;
    Ok(root.join("linux-app-manager/state.sqlite3"))
}

fn unix_now() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs() as i64)
        .unwrap_or_default()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::Source;

    #[test]
    fn cache_and_history_survive_a_store_reopen() {
        let path = std::env::temp_dir().join(format!(
            "linux-app-manager-state-{}-{}.sqlite3",
            std::process::id(),
            unix_now()
        ));
        let app = InstalledApplication::new(Source::Apt, "firefox");
        let provider = ProviderStatus {
            source: Source::Apt,
            available: true,
            healthy: true,
            item_count: 1,
            message: None,
        };
        {
            let store = StateStore::open(&path).unwrap();
            store.record_scan(&[app], &[provider]).unwrap();
            store
                .record_operation(OperationInput {
                    action: "uninstall",
                    app_id: "apt:firefox",
                    app_name: "Firefox",
                    source: "apt",
                    clean: false,
                    status: "success",
                    exit_code: Some(0),
                    output: Some("done"),
                })
                .unwrap();
        }
        let store = StateStore::open(&path).unwrap();
        let cache = store.latest_scan().unwrap().unwrap();
        assert_eq!(cache.apps[0].package_name.as_deref(), Some("firefox"));
        assert!(cache.providers[0].healthy);
        let history = store.history(10).unwrap();
        assert_eq!(history.len(), 1);
        assert_eq!(history[0].status, "success");
        let _ = std::fs::remove_file(path);
    }
}
