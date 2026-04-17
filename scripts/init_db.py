from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import text

from app.db import engine


DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_key TEXT NOT NULL UNIQUE,
    provider_name TEXT NOT NULL,
    base_url TEXT NOT NULL,
    api_key_env TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id INTEGER NOT NULL,
    model_key TEXT NOT NULL,
    model_name TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (provider_id) REFERENCES providers(id) ON DELETE CASCADE,
    UNIQUE (provider_id, model_key)
);

CREATE TABLE IF NOT EXISTS probe_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id INTEGER NOT NULL,
    model_id INTEGER NOT NULL,
    run_type TEXT NOT NULL,
    success INTEGER NOT NULL,
    http_status INTEGER,
    error_type TEXT,
    error_message TEXT,
    latency_ms REAL,
    ttft_ms REAL,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    cached_tokens INTEGER,
    tokens_per_sec REAL,
    request_payload TEXT,
    response_payload TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (provider_id) REFERENCES providers(id) ON DELETE CASCADE,
    FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_probe_runs_provider_model_time
ON probe_runs(provider_id, model_id, created_at);

CREATE INDEX IF NOT EXISTS idx_probe_runs_type_time
ON probe_runs(run_type, created_at);

CREATE TABLE IF NOT EXISTS eval_sets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    eval_key TEXT NOT NULL UNIQUE,
    eval_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    dataset_path TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS eval_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    eval_set_id INTEGER NOT NULL,
    provider_id INTEGER NOT NULL,
    model_id INTEGER NOT NULL,
    score REAL NOT NULL,
    passed_count INTEGER NOT NULL DEFAULT 0,
    total_count INTEGER NOT NULL DEFAULT 0,
    detail_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (eval_set_id) REFERENCES eval_sets(id) ON DELETE CASCADE,
    FOREIGN KEY (provider_id) REFERENCES providers(id) ON DELETE CASCADE,
    FOREIGN KEY (model_id) REFERENCES models(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_eval_results_lookup
ON eval_results(eval_set_id, provider_id, model_id, created_at);

CREATE TABLE IF NOT EXISTS app_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_key TEXT NOT NULL UNIQUE,
    job_name TEXT NOT NULL,
    cron_expr TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    last_run_at TEXT,
    next_run_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def main() -> None:
    (ROOT_DIR / "data").mkdir(parents=True, exist_ok=True)
    statements = [stmt.strip() for stmt in DDL.split(";") if stmt.strip()]
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
    print("Database initialized.")


if __name__ == "__main__":
    main()
