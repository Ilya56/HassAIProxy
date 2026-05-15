from fastapi.testclient import TestClient

from homeassistant_proxy.config import get_settings
from homeassistant_proxy.db.session import SqliteStore
from homeassistant_proxy.main import create_app
from homeassistant_proxy.services.audit_service import AuditService


def _client(monkeypatch, tmp_path) -> TestClient:
    monkeypatch.setenv("APP_API_KEY", "test-key")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "audit.sqlite3"))
    get_settings.cache_clear()
    return TestClient(create_app())


def _auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-key"}


def _record_logs(sqlite_path: str) -> list[str]:
    service = AuditService(SqliteStore(sqlite_path))
    service.record(
        action_type="apply_draft",
        resource_type="draft",
        resource_id="draft-1",
        request_summary="Apply draft one",
        result="ok",
        error_message=None,
        created_at="2026-05-15T10:00:00+00:00",
        actor="owner",
    )
    service.record(
        action_type="rollback_draft",
        resource_type="draft",
        resource_id="draft-1",
        request_summary="Rollback draft one",
        result="failed",
        error_message="Rollback failed.",
        created_at="2026-05-15T11:00:00+00:00",
        actor="owner",
    )
    return [log.id for log in service.list_logs(limit=10)]


def test_audit_logs_require_auth(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)

    response = client.get("/audit/logs")

    assert response.status_code == 401
    assert response.json()["code"] == "auth.missing_bearer_token"
    get_settings.cache_clear()


def test_list_audit_logs_returns_recent_logs(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    _record_logs(str(tmp_path / "audit.sqlite3"))

    response = client.get("/audit/logs", headers=_auth_headers())

    assert response.status_code == 200
    logs = response.json()["logs"]
    assert [log["action_type"] for log in logs] == ["rollback_draft", "apply_draft"]
    assert logs[0]["result"] == "failed"
    assert logs[0]["error_message"] == "Rollback failed."
    assert logs[1]["actor"] == "owner"
    get_settings.cache_clear()


def test_list_audit_logs_filters_and_limits(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    _record_logs(str(tmp_path / "audit.sqlite3"))

    response = client.get(
        "/audit/logs",
        headers=_auth_headers(),
        params={
            "action_type": "apply_draft",
            "resource_type": "draft",
            "status": "ok",
            "date_from": "2026-05-15T09:00:00+00:00",
            "date_to": "2026-05-15T10:30:00+00:00",
            "limit": 1,
        },
    )

    assert response.status_code == 200
    logs = response.json()["logs"]
    assert len(logs) == 1
    assert logs[0]["action_type"] == "apply_draft"
    assert logs[0]["resource_id"] == "draft-1"
    get_settings.cache_clear()


def test_get_audit_log_returns_one_log(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)
    log_ids = _record_logs(str(tmp_path / "audit.sqlite3"))

    response = client.get(f"/audit/logs/{log_ids[0]}", headers=_auth_headers())

    assert response.status_code == 200
    assert response.json()["id"] == log_ids[0]
    assert response.json()["action_type"] == "rollback_draft"
    get_settings.cache_clear()


def test_get_audit_log_maps_missing_id(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)

    response = client.get("/audit/logs/missing", headers=_auth_headers())

    assert response.status_code == 404
    assert response.json()["code"] == "audit.not_found"
    get_settings.cache_clear()


def test_audit_log_limit_validation(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)

    response = client.get("/audit/logs", headers=_auth_headers(), params={"limit": 201})

    assert response.status_code == 422
    get_settings.cache_clear()
