import os
from hashlib import sha256

from fastapi.testclient import TestClient

from homeassistant_proxy.config import get_settings
from homeassistant_proxy.main import create_app


def _client(monkeypatch, tmp_path) -> TestClient:
    monkeypatch.setenv("APP_API_KEY", "test-key")
    monkeypatch.setenv("ACTOR_NAME", "owner")
    monkeypatch.setenv("CONFIG_ROOT", str(tmp_path / "config"))
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "drafts.sqlite3"))
    monkeypatch.setenv("ALLOWED_READ_GLOBS", "/config/configuration.yaml,/config/packages/ai/*.yaml")
    if "ALLOWED_WRITE_GLOBS" not in os.environ:
        monkeypatch.setenv("ALLOWED_WRITE_GLOBS", "/config/packages/ai/*.yaml")
    get_settings.cache_clear()
    return TestClient(create_app())


def _auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-key"}


def test_create_draft_for_new_ai_package_file(monkeypatch, tmp_path) -> None:
    (tmp_path / "config" / "packages" / "ai").mkdir(parents=True)
    client = _client(monkeypatch, tmp_path)

    response = client.post(
        "/drafts/create",
        headers=_auth_headers(),
        json={
            "target_path": "/config/packages/ai/co2.yaml",
            "operation_type": "create",
            "proposed_content": "automation: []\n",
            "summary": "Add CO2 automation package",
            "reason": "Prepare a new AI-owned package file.",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["target_path"] == "/config/packages/ai/co2.yaml"
    assert body["operation_type"] == "create"
    assert body["status"] == "ready_for_approval"
    assert body["created_by"] == "owner"
    assert body["base_hash"] is None
    assert "--- /config/packages/ai/co2.yaml" in body["diff_text"]
    assert "+++ /config/packages/ai/co2.yaml" in body["diff_text"]
    assert "+automation: []" in body["diff_text"]
    assert str(tmp_path) not in body["diff_text"]
    assert not (tmp_path / "config" / "packages" / "ai" / "co2.yaml").exists()
    get_settings.cache_clear()


def test_get_draft_and_diff(monkeypatch, tmp_path) -> None:
    (tmp_path / "config" / "packages" / "ai").mkdir(parents=True)
    client = _client(monkeypatch, tmp_path)
    create_response = client.post(
        "/drafts/create",
        headers=_auth_headers(),
        json={
            "target_path": "/config/packages/ai/light.yaml",
            "operation_type": "create",
            "proposed_content": "script: {}\n",
            "summary": "Add light script package",
            "reason": "Prepare package file.",
        },
    )
    draft_id = create_response.json()["id"]

    draft_response = client.get(f"/drafts/{draft_id}", headers=_auth_headers())
    diff_response = client.get(f"/drafts/{draft_id}/diff", headers=_auth_headers())

    assert draft_response.status_code == 200
    assert draft_response.json()["id"] == draft_id
    assert diff_response.status_code == 200
    assert diff_response.json()["draft_id"] == draft_id
    assert diff_response.json()["summary"] == "Add light script package"
    assert "+script: {}" in diff_response.json()["diff_text"]
    get_settings.cache_clear()


def test_create_update_draft_requires_matching_base_hash(monkeypatch, tmp_path) -> None:
    config_file = tmp_path / "config" / "packages" / "ai" / "co2.yaml"
    config_file.parent.mkdir(parents=True)
    original_content = "automation: []\n"
    config_file.write_text(original_content, encoding="utf-8")
    base_hash = sha256(original_content.encode("utf-8")).hexdigest()
    client = _client(monkeypatch, tmp_path)

    response = client.post(
        "/drafts/create",
        headers=_auth_headers(),
        json={
            "target_path": "/config/packages/ai/co2.yaml",
            "operation_type": "update",
            "base_hash": base_hash,
            "proposed_content": "automation:\n  - alias: CO2 ventilation\n",
            "summary": "Update CO2 automation",
            "reason": "Prepare safer ventilation automation.",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["base_hash"] == base_hash
    assert "-automation: []" in body["diff_text"]
    assert "+automation:" in body["diff_text"]
    get_settings.cache_clear()


def test_create_update_draft_rejects_stale_base_hash(monkeypatch, tmp_path) -> None:
    config_file = tmp_path / "config" / "packages" / "ai" / "co2.yaml"
    config_file.parent.mkdir(parents=True)
    config_file.write_text("automation: []\n", encoding="utf-8")
    client = _client(monkeypatch, tmp_path)

    response = client.post(
        "/drafts/create",
        headers=_auth_headers(),
        json={
            "target_path": "/config/packages/ai/co2.yaml",
            "operation_type": "update",
            "base_hash": "wrong",
            "proposed_content": "automation: []\n",
            "summary": "Update CO2 automation",
            "reason": "Prepare update.",
        },
    )

    assert response.status_code == 409
    assert response.json()["code"] == "drafts.base_hash_mismatch"
    get_settings.cache_clear()


def test_validate_draft_reports_hash_mismatch_after_file_changes(monkeypatch, tmp_path) -> None:
    config_file = tmp_path / "config" / "packages" / "ai" / "co2.yaml"
    config_file.parent.mkdir(parents=True)
    original_content = "automation: []\n"
    config_file.write_text(original_content, encoding="utf-8")
    base_hash = sha256(original_content.encode("utf-8")).hexdigest()
    client = _client(monkeypatch, tmp_path)
    create_response = client.post(
        "/drafts/create",
        headers=_auth_headers(),
        json={
            "target_path": "/config/packages/ai/co2.yaml",
            "operation_type": "update",
            "base_hash": base_hash,
            "proposed_content": "automation:\n  - alias: CO2 ventilation\n",
            "summary": "Update CO2 automation",
            "reason": "Prepare update.",
        },
    )
    config_file.write_text("automation:\n  - alias: Other change\n", encoding="utf-8")

    response = client.post(f"/drafts/{create_response.json()['id']}/validate", headers=_auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert "The target file has changed since draft creation." in body["errors"]
    get_settings.cache_clear()


def test_create_draft_rejects_delete_and_invalid_yaml(monkeypatch, tmp_path) -> None:
    (tmp_path / "config" / "packages" / "ai").mkdir(parents=True)
    client = _client(monkeypatch, tmp_path)

    delete_response = client.post(
        "/drafts/create",
        headers=_auth_headers(),
        json={
            "target_path": "/config/packages/ai/co2.yaml",
            "operation_type": "delete",
            "proposed_content": "",
            "summary": "Delete package",
            "reason": "Not supported yet.",
        },
    )
    invalid_yaml_response = client.post(
        "/drafts/create",
        headers=_auth_headers(),
        json={
            "target_path": "/config/packages/ai/co2.yaml",
            "operation_type": "create",
            "proposed_content": "automation: [\n",
            "summary": "Add broken package",
            "reason": "Exercise validation.",
        },
    )

    assert delete_response.status_code == 422
    assert delete_response.json()["code"] == "drafts.delete_not_supported"
    assert invalid_yaml_response.status_code == 422
    assert invalid_yaml_response.json()["code"] == "drafts.validation_failed"
    get_settings.cache_clear()


def test_create_draft_rejects_paths_outside_direct_ai_package_yaml(monkeypatch, tmp_path) -> None:
    (tmp_path / "config" / "packages" / "ai" / "nested").mkdir(parents=True)
    client = _client(monkeypatch, tmp_path)

    response = client.post(
        "/drafts/create",
        headers=_auth_headers(),
        json={
            "target_path": "/config/packages/ai/nested/co2.yaml",
            "operation_type": "create",
            "proposed_content": "automation: []\n",
            "summary": "Add nested package",
            "reason": "Nested paths are outside v1.",
        },
    )

    assert response.status_code == 403
    assert response.json()["code"] == "files.path_not_writable"
    get_settings.cache_clear()


def test_create_draft_follows_configured_write_globs(monkeypatch, tmp_path) -> None:
    (tmp_path / "config" / "packages" / "ai" / "nested").mkdir(parents=True)
    monkeypatch.setenv("ALLOWED_WRITE_GLOBS", "/config/packages/ai/**/*.yaml")
    client = _client(monkeypatch, tmp_path)

    response = client.post(
        "/drafts/create",
        headers=_auth_headers(),
        json={
            "target_path": "/config/packages/ai/nested/co2.yaml",
            "operation_type": "create",
            "proposed_content": "automation: []\n",
            "summary": "Add nested package",
            "reason": "Configured write globs allow this path.",
        },
    )

    assert response.status_code == 201
    assert response.json()["target_path"] == "/config/packages/ai/nested/co2.yaml"
    get_settings.cache_clear()


def test_readonly_mode_allows_draft_creation(monkeypatch, tmp_path) -> None:
    (tmp_path / "config" / "packages" / "ai").mkdir(parents=True)
    monkeypatch.setenv("READONLY_MODE", "true")
    client = _client(monkeypatch, tmp_path)

    response = client.post(
        "/drafts/create",
        headers=_auth_headers(),
        json={
            "target_path": "/config/packages/ai/co2.yaml",
            "operation_type": "create",
            "proposed_content": "automation: []\n",
            "summary": "Add CO2 package",
            "reason": "Drafts are allowed in read-only mode.",
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "ready_for_approval"
    get_settings.cache_clear()
