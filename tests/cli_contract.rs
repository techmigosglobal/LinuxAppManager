use std::process::Command;

use serde_json::Value;

fn lam() -> Command {
    let binary = std::env::var("CARGO_BIN_EXE_lam").unwrap_or_else(|_| {
        std::env::var("LAM_BIN")
            .unwrap_or_else(|_| format!("{}/target/debug/lam", env!("CARGO_MANIFEST_DIR")))
    });
    Command::new(binary)
}

#[test]
fn list_json_exposes_provider_health_and_partial_scan_errors() {
    let state_dir = std::env::temp_dir().join(format!(
        "linux-app-manager-list-state-{}",
        std::process::id()
    ));
    let output = lam()
        .args(["list", "--json"])
        .env("XDG_STATE_HOME", &state_dir)
        .output()
        .expect("lam should start");
    assert!(output.status.success(), "lam failed: {:?}", output);
    let payload: Value = serde_json::from_slice(&output.stdout).expect("valid list JSON");
    let providers = payload["providers"].as_array().expect("providers array");
    assert!(!providers.is_empty());
    for provider in providers {
        assert!(provider["source"].is_string());
        assert!(provider["available"].is_boolean());
        assert!(provider["healthy"].is_boolean());
        assert!(provider["item_count"].is_u64());
        if provider["healthy"] == false {
            assert!(provider["message"].is_string());
        }
    }
    assert!(payload["state_warning"].is_null() || payload["state_warning"].is_string());
    let _ = std::fs::remove_dir_all(state_dir);
}

#[test]
fn invalid_removal_input_is_rejected_without_running_a_command() {
    let output = lam()
        .args(["plan-remove", "not-a-real-package;run-something", "--json"])
        .output()
        .expect("lam should start");
    assert!(
        output.status.success(),
        "JSON error should be returned as data"
    );
    let payload: Value = serde_json::from_slice(&output.stdout).expect("valid removal JSON");
    assert_eq!(payload["ok"], false);
    assert!(payload["error"]
        .as_str()
        .unwrap_or_default()
        .contains("No application"));
}

#[test]
fn history_command_returns_json_without_mutating_packages() {
    let state_dir = std::env::temp_dir().join(format!(
        "linux-app-manager-cli-state-{}",
        std::process::id()
    ));
    let output = lam()
        .args(["history", "--json"])
        .env("XDG_STATE_HOME", &state_dir)
        .output()
        .expect("lam should start");
    assert!(output.status.success(), "history failed: {:?}", output);
    let payload: Value = serde_json::from_slice(&output.stdout).expect("valid history JSON");
    assert!(payload.is_array());
    let _ = std::fs::remove_dir_all(state_dir);
}

#[test]
fn sandboxed_cli_blocks_host_mutations_before_scanning_or_authorizing() {
    let output = lam()
        .args(["uninstall", "apt:editor", "--yes"])
        .env("SNAP", "/snap/linux-app-manager/current")
        .output()
        .expect("lam should start");
    assert_eq!(output.status.code(), Some(2));
    assert!(String::from_utf8_lossy(&output.stderr).contains("disabled in sandboxed builds"));
}
