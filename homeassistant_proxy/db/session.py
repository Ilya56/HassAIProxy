from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS drafts (
    id TEXT PRIMARY KEY,
    target_path TEXT NOT NULL,
    operation_type TEXT NOT NULL,
    base_hash TEXT,
    proposed_content TEXT NOT NULL,
    diff_text TEXT NOT NULL,
    summary TEXT NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    validated_at TEXT,
    applied_at TEXT,
    created_by TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS file_versions (
    id TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    content_hash TEXT,
    backup_path TEXT,
    previous_existed INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    related_draft_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    action_type TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT,
    request_summary TEXT NOT NULL,
    result TEXT NOT NULL,
    error_message TEXT,
    created_at TEXT NOT NULL,
    actor TEXT NOT NULL
);
"""


class SqliteStore:
    def __init__(self, sqlite_path: str) -> None:
        self._sqlite_path = sqlite_path
        if sqlite_path != ":memory:":
            Path(sqlite_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._sqlite_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA_SQL)
