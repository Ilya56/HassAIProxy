from __future__ import annotations

from sqlite3 import Row
from uuid import uuid4

from homeassistant_proxy.core.errors import ApiError
from homeassistant_proxy.db.session import SqliteStore
from homeassistant_proxy.models.api_models import AuditLog


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

    def list_logs(
        self,
        *,
        action_type: str | None = None,
        resource_type: str | None = None,
        status: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 50,
    ) -> list[AuditLog]:
        safe_limit = max(1, min(limit, 200))
        clauses: list[str] = []
        params: list[str | int] = []

        if action_type is not None:
            clauses.append("action_type = ?")
            params.append(action_type)
        if resource_type is not None:
            clauses.append("resource_type = ?")
            params.append(resource_type)
        if status is not None:
            clauses.append("result = ?")
            params.append(status)
        if date_from is not None:
            clauses.append("created_at >= ?")
            params.append(date_from)
        if date_to is not None:
            clauses.append("created_at <= ?")
            params.append(date_to)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._store.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM audit_logs
                {where_sql}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (*params, safe_limit),
            ).fetchall()

        return [_row_to_audit_log(row) for row in rows]

    def get_log(self, log_id: str) -> AuditLog:
        with self._store.connect() as connection:
            row = connection.execute("SELECT * FROM audit_logs WHERE id = ?", (log_id,)).fetchone()
        if row is None:
            raise ApiError(
                status_code=404,
                code="audit.not_found",
                message="The requested audit log entry was not found.",
                retryable=False,
                details={"log_id": log_id},
            )
        return _row_to_audit_log(row)


def _row_to_audit_log(row: Row) -> AuditLog:
    return AuditLog(
        id=row["id"],
        action_type=row["action_type"],
        resource_type=row["resource_type"],
        resource_id=row["resource_id"],
        request_summary=row["request_summary"],
        result=row["result"],
        error_message=row["error_message"],
        created_at=row["created_at"],
        actor=row["actor"],
    )
