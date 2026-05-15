from __future__ import annotations

from uuid import uuid4

from homeassistant_proxy.db.session import SqliteStore


class AuditService:
    def __init__(self, store: SqliteStore) -> None:
        self._store = store

    def record(
        self,
        *,
        action_type: str,
        resource_type: str,
        resource_id: str | None,
        request_summary: str,
        result: str,
        error_message: str | None,
        created_at: str,
        actor: str,
    ) -> None:
        with self._store.connect() as connection:
            connection.execute(
                """
                INSERT INTO audit_logs (
                    id, action_type, resource_type, resource_id, request_summary,
                    result, error_message, created_at, actor
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    action_type,
                    resource_type,
                    resource_id,
                    request_summary,
                    result,
                    error_message,
                    created_at,
                    actor,
                ),
            )
