CREATE TABLE IF NOT EXISTS agent_daily_cleanup (
    id BIGSERIAL PRIMARY KEY,
    executed_at TIMESTAMPTZ NOT NULL,
    project_id TEXT NOT NULL,
    site_key TEXT NOT NULL,
    agent_url TEXT NOT NULL,
    retention_days INTEGER NOT NULL,
    status_code INTEGER,
    deleted_count INTEGER,
    duration_ms INTEGER NOT NULL,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_agent_daily_cleanup_executed_at
    ON agent_daily_cleanup (executed_at DESC);

CREATE TABLE IF NOT EXISTS agent_daily_error_count (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL,
    project_id TEXT NOT NULL,
    site_key TEXT NOT NULL,
    success BOOLEAN NOT NULL,
    agent_error TEXT,
    error_count INTEGER,
    recorded_at TIMESTAMPTZ NOT NULL,
    UNIQUE (project_id, site_key, date)
);

CREATE INDEX IF NOT EXISTS idx_agent_daily_error_count_date
    ON agent_daily_error_count (date DESC);
