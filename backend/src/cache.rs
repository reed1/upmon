use std::collections::HashMap;
use std::path::Path;

use tracing::{info, warn};

use crate::models::{CacheEntry, StatusCache};

pub fn load(path: &Path) -> HashMap<(String, String), CacheEntry> {
    let bytes = match std::fs::read(path) {
        Ok(b) => b,
        Err(e) => {
            warn!(path = %path.display(), error = %e, "could not read cache file, starting fresh");
            return HashMap::new();
        }
    };

    let entries: Vec<CacheEntry> = match serde_json::from_slice(&bytes) {
        Ok(v) => v,
        Err(e) => {
            warn!(path = %path.display(), error = %e, "could not parse cache file, starting fresh");
            return HashMap::new();
        }
    };

    let count = entries.len();
    let map = entries
        .into_iter()
        .map(|e| ((e.result.project_id.clone(), e.result.site_key.clone()), e))
        .collect();
    info!(path = %path.display(), count, "loaded cache from disk");
    map
}

pub fn save(path: &Path, cache: &StatusCache) {
    let entries: Vec<CacheEntry> = cache.read().unwrap().values().cloned().collect();
    let json = match serde_json::to_string_pretty(&entries) {
        Ok(j) => j,
        Err(e) => {
            warn!(error = %e, "failed to serialize cache");
            return;
        }
    };

    let tmp = path.with_extension("json.tmp");
    if let Err(e) = std::fs::write(&tmp, &json) {
        warn!(path = %tmp.display(), error = %e, "failed to write temp cache file");
        return;
    }
    if let Err(e) = std::fs::rename(&tmp, path) {
        warn!(from = %tmp.display(), to = %path.display(), error = %e, "failed to rename cache file");
    }
}
