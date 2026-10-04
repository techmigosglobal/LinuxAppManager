use std::path::Path;

pub fn human_size(b: u64) -> String {
    const U: [&str; 5] = ["B", "KB", "MB", "GB", "TB"];
    let (mut v, mut i) = (b as f64, 0);
    while v >= 1024.0 && i < 4 {
        v /= 1024.0;
        i += 1;
    }
    if i == 0 {
        format!("{} B", b)
    } else {
        format!("{:.1} {}", v, U[i])
    }
}

/// Parses sizes such as "312.5 MB" (decimal units, as printed by flatpak).
pub fn parse_size(s: &str) -> Option<u64> {
    let s = s.replace('\u{a0}', " ");
    let mut it = s.split_whitespace();
    let n: f64 = it.next()?.replace(',', ".").parse().ok()?;
    let mult = match it.next().unwrap_or("bytes") {
        "bytes" | "B" => 1.0,
        "kB" | "KB" => 1e3,
        "MB" => 1e6,
        "GB" => 1e9,
        "TB" => 1e12,
        _ => return None,
    };
    Some((n * mult) as u64)
}

/// Recursive size that never follows symlinks (safe for cache/config previews).
pub fn dir_size(path: &Path) -> u64 {
    let Ok(md) = std::fs::symlink_metadata(path) else {
        return 0;
    };
    if md.is_file() {
        return md.len();
    }
    if !md.is_dir() {
        return 0;
    }
    std::fs::read_dir(path)
        .map(|rd| rd.flatten().map(|e| dir_size(&e.path())).sum())
        .unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn sizes() {
        assert_eq!(human_size(1536), "1.5 KB");
        assert_eq!(parse_size("312.5 MB"), Some(312_500_000));
        assert_eq!(parse_size("12 bytes"), Some(12));
        assert_eq!(parse_size("abc"), None);
    }
}
