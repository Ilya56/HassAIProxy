from hashlib import sha256

from fastapi.testclient import TestClient

from homeassistant_proxy.config import get_settings
from homeassistant_proxy.main import create_app


def _client(monkeypatch, tmp_path) -> TestClient:
    monkeypatch.setenv("APP_API_KEY", "test-key")
    monkeypatch.setenv("CONFIG_ROOT", str(tmp_path))
    monkeypatch.setenv("ALLOWED_READ_GLOBS", "/config/configuration.yaml,/config/packages/ai/*.yaml")
    monkeypatch.setenv("ALLOWED_WRITE_GLOBS", "/config/packages/ai/*.yaml")
    get_settings.cache_clear()
    return TestClient(create_app())


def test_read_allowed_file_returns_ha_style_path(monkeypatch, tmp_path) -> None:
    config_file = tmp_path / "packages" / "ai" / "test.yaml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("automation: []\n", encoding="utf-8")
    client = _client(monkeypatch, tmp_path)

    response = client.get(
        "/files/read",
        params={"path": "/config/packages/ai/test.yaml"},
        headers={"Authorization": "Bearer test-key"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "path": "/config/packages/ai/test.yaml",
        "content": "automation: []\n",
        "content_hash": sha256("automation: []\n".encode("utf-8")).hexdigest(),
    }
    get_settings.cache_clear()


def test_read_forbidden_secrets_yaml(monkeypatch, tmp_path) -> None:
    (tmp_path / "secrets.yaml").write_text("token: nope\n", encoding="utf-8")
    client = _client(monkeypatch, tmp_path)

    response = client.get(
        "/files/read",
        params={"path": "/config/secrets.yaml"},
        headers={"Authorization": "Bearer test-key"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "files.forbidden_path"
    get_settings.cache_clear()


def test_read_rejects_path_traversal(monkeypatch, tmp_path) -> None:
    client = _client(monkeypatch, tmp_path)

    response = client.get(
        "/files/read",
        params={"path": "/config/packages/ai/../../secrets.yaml"},
        headers={"Authorization": "Bearer test-key"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "files.path_escape"
    get_settings.cache_clear()


def test_metadata_returns_hash_size_modified_time_and_writable(monkeypatch, tmp_path) -> None:
    content = "script: {}\n"
    config_file = tmp_path / "packages" / "ai" / "test.yaml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text(content, encoding="utf-8")
    client = _client(monkeypatch, tmp_path)

    response = client.get(
        "/files/metadata",
        params={"path": "/config/packages/ai/test.yaml"},
        headers={"Authorization": "Bearer test-key"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["path"] == "/config/packages/ai/test.yaml"
    assert body["writable"] is True
    assert body["size_bytes"] == config_file.stat().st_size
    assert body["content_hash"] == sha256(content.encode("utf-8")).hexdigest()
    assert body["modified_at"].endswith("+00:00")
    get_settings.cache_clear()


def test_list_allowed_files(monkeypatch, tmp_path) -> None:
    (tmp_path / "configuration.yaml").write_text("homeassistant: {}\n", encoding="utf-8")
    ai_file = tmp_path / "packages" / "ai" / "test.yaml"
    ai_file.parent.mkdir(parents=True)
    ai_file.write_text("automation: []\n", encoding="utf-8")
    client = _client(monkeypatch, tmp_path)

    response = client.get("/files/list", headers={"Authorization": "Bearer test-key"})

    assert response.status_code == 200
    assert [file["path"] for file in response.json()["files"]] == [
        "/config/configuration.yaml",
        "/config/packages/ai/test.yaml",
    ]
    get_settings.cache_clear()
