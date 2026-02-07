CREATE TABLE monitor_checks (
    id          BIGSERIAL    PRIMARY KEY,
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

CREATE INDEX idx_monitor_checks_monitor_time
    ON monitor_checks (project_id, site_key, checked_at DESC);

CREATE INDEX idx_monitor_checks_checked_at
    ON monitor_checks (checked_at);

CREATE TABLE monitor_status (
    project_id  TEXT        NOT NULL,
    site_key    TEXT        NOT NULL,
    url         TEXT        NOT NULL,
    status_code SMALLINT,
    response_ms INT         NOT NULL,
    is_up       BOOLEAN     NOT NULL,
    error_type  TEXT,
    error_message TEXT,
    checked_at    TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (project_id, site_key)
);

CREATE OR REPLACE FUNCTION update_monitor_status() RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO monitor_status (project_id, site_key, url, status_code, response_ms, is_up, error_type, error_message, checked_at)
    VALUES (NEW.project_id, NEW.site_key, NEW.url, NEW.status_code, NEW.response_ms, NEW.is_up, NEW.error_type, NEW.error_message, NEW.checked_at)
    ON CONFLICT (project_id, site_key)
    DO UPDATE SET
        url         = EXCLUDED.url,
        status_code = EXCLUDED.status_code,
        response_ms = EXCLUDED.response_ms,
        is_up       = EXCLUDED.is_up,
        error_type  = EXCLUDED.error_type,
        error_message = EXCLUDED.error_message,
        checked_at  = EXCLUDED.checked_at
    WHERE EXCLUDED.checked_at >= monitor_status.checked_at;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_monitor_status
    AFTER INSERT ON monitor_checks
    FOR EACH ROW
    EXECUTE FUNCTION update_monitor_status();
