CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE monitor_checks (
    project_id  TEXT         NOT NULL,
    site_key    TEXT         NOT NULL,
    url         TEXT         NOT NULL,
    status_code SMALLINT,
    response_ms INT          NOT NULL,
    is_up       BOOLEAN      NOT NULL,
    error_type  TEXT,
    error_message TEXT,
    checked_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

SELECT create_hypertable('monitor_checks', 'checked_at');

CREATE INDEX idx_monitor_checks_monitor_time
    ON monitor_checks (project_id, site_key, checked_at DESC);

CREATE TABLE monitor_status (
    project_id      TEXT         NOT NULL,
    site_key        TEXT         NOT NULL,
    url             TEXT         NOT NULL,
    status_code     SMALLINT,
    response_ms     INT          NOT NULL,
    is_up           BOOLEAN      NOT NULL,
    error_type      TEXT,
    error_message   TEXT,
    last_checked_at TIMESTAMPTZ  NOT NULL,
    last_up_at      TIMESTAMPTZ,
    PRIMARY KEY (project_id, site_key)
);
