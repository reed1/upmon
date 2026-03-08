CREATE TABLE IF NOT EXISTS agent_cleanup_log (
    id BIGSERIAL PRIMARY KEY,
    executed_at TIMESTAMPTZ NOT NULL,
    project_id TEXT NOT NULL,
    site_key TEXT NOT NULL,
    agent_url TEXT NOT NULL,
    retention_days INTEGER NOT NULL,
    status_code INTEGER,
    deleted_count INTEGER,
    duration_ms INTEGER NOT NULL,
    error TEXT
);
