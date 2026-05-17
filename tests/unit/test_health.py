from fastapi.testclient import TestClient

from homeassistant_proxy.config import get_settings
from homeassistant_proxy.core.errors import ApiError
from homeassistant_proxy.main import create_app
from homeassistant_proxy.services.file_backends import FileBackendStat


def test_health_requires_bearer_token() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 401
    assert response.json()["code"] == "auth.missing_bearer_token"


def test_health_returns_status_with_valid_token(monkeypatch) -> None:
    monkeypatch.setenv("APP_API_KEY", "test-key")
    get_settings.cache_clear()
    client = TestClient(create_app())

    response = client.get("/health", headers={"Authorization": "Bearer test-key"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"
    assert body["ha_reachable"] is False
    assert isinstance(body["file_storage_ok"], bool)
    get_settings.cache_clear()


def test_health_reports_sftp_storage_failure(monkeypatch) -> None:
    class BrokenBackend:
        async def list_files(self, relative_dir: str) -> list[str]:
            return []

        async def read_text(self, relative_path: str) -> str:
            return ""

        async def stat(self, relative_path: str) -> FileBackendStat:
            raise AssertionError("stat should not be used by health")

        async def check_access(self) -> None:
            raise ApiError(
                status_code=502,
                code="files.remote_transport_error",
                message="Remote file transport failed.",
                retryable=True,
            )

        async def write_text(self, relative_path: str, content: str) -> None:
            return None

        async def delete_file(self, relative_path: str) -> None:
            return None

    monkeypatch.setenv("APP_API_KEY", "test-key")
    monkeypatch.setenv("FILE_BACKEND", "sftp")
    monkeypatch.setenv("SFTP_HOST", "homeassistant.local")
    monkeypatch.setenv("SFTP_PRIVATE_KEY_PATH", "./secrets/ha_proxy_sftp_key")
    monkeypatch.setattr("homeassistant_proxy.services.file_service.build_file_backend", lambda settings: BrokenBackend())
    get_settings.cache_clear()
    client = TestClient(create_app())

    response = client.get("/health", headers={"Authorization": "Bearer test-key"})

    assert response.status_code == 200
    assert response.json()["file_storage_ok"] is False
    get_settings.cache_clear()
