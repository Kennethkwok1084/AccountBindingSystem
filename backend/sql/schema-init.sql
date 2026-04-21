-- PostgreSQL initialization reference.
-- This file is only for greenfield bootstrap/reference.
-- Use Alembic migrations for production schema changes.

CREATE TABLE IF NOT EXISTS system_config (
    config_key VARCHAR(64) PRIMARY KEY,
    config_value JSONB NOT NULL,
    remark VARCHAR(255),
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

