CREATE TABLE check_results (
    id          BIGSERIAL    PRIMARY KEY,
    project_id  TEXT         NOT NULL,
    site_key    TEXT         NOT NULL,
    url         TEXT         NOT NULL,
    status_code SMALLINT,
    response_ms INT          NOT NULL,
    is_up       BOOLEAN      NOT NULL,
    error       TEXT,
    checked_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_check_results_monitor_time
    ON check_results (project_id, site_key, checked_at DESC);

CREATE INDEX idx_check_results_checked_at
    ON check_results (checked_at);
