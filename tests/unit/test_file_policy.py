import pytest

from homeassistant_proxy.config import Settings
from homeassistant_proxy.core.errors import ApiError
from homeassistant_proxy.services.file_policy import FilePathPolicy, ResolvedFilePath


def test_file_policy_resolves_allowed_read_path_to_backend_relative_path() -> None:
    policy = FilePathPolicy(Settings())

    resolved = policy.resolve_read_path("/config/packages/ai/test.yaml")

    assert resolved == ResolvedFilePath(
        api_path="/config/packages/ai/test.yaml",
        relative_path="packages/ai/test.yaml",
    )


def test_file_policy_normalizes_windows_separators_for_api_paths() -> None:
    policy = FilePathPolicy(Settings())

    resolved = policy.resolve_read_path(r"\config\packages\ai\test.yaml")

    assert resolved.api_path == "/config/packages/ai/test.yaml"
    assert resolved.relative_path == "packages/ai/test.yaml"


def test_file_policy_rejects_non_config_paths() -> None:
    policy = FilePathPolicy(Settings())

    with pytest.raises(ApiError) as exc_info:
        policy.resolve_read_path("packages/ai/test.yaml")

    assert exc_info.value.code == "files.path_not_allowed"


def test_file_policy_rejects_path_traversal() -> None:
    policy = FilePathPolicy(Settings())

    with pytest.raises(ApiError) as exc_info:
        policy.resolve_read_path("/config/packages/ai/../../secrets.yaml")

    assert exc_info.value.code == "files.path_escape"


@pytest.mark.parametrize(
    "path",
    [
        "/config/secrets.yaml",
        "/config/.storage/core.config_entries",
        "/config/backups/backup.tar",
        "/config/ssl/fullchain.pem",
        "/config/home-assistant_v2.db",
        "/config/packages/ai/.hidden.yaml",
    ],
)
def test_file_policy_rejects_forbidden_paths(path: str) -> None:
    policy = FilePathPolicy(
        Settings(
            allowed_read_globs=[
                "/config/*.yaml",
                "/config/*.db",
                "/config/.storage/*",
                "/config/backups/*",
                "/config/ssl/*",
                "/config/packages/ai/*.yaml",
            ]
        )
    )

    with pytest.raises(ApiError) as exc_info:
        policy.resolve_read_path(path)

    assert exc_info.value.code == "files.forbidden_path"


def test_file_policy_keeps_main_files_read_only_by_default() -> None:
    policy = FilePathPolicy(Settings())

    assert policy.resolve_read_path("/config/automations.yaml").api_path == "/config/automations.yaml"

    with pytest.raises(ApiError) as exc_info:
        policy.resolve_write_path("/config/automations.yaml")

    assert exc_info.value.code == "files.path_not_writable"


def test_file_policy_allows_default_ai_package_write_path() -> None:
    policy = FilePathPolicy(Settings())

    resolved = policy.resolve_write_path("/config/packages/ai/generated.yaml")

    assert resolved == ResolvedFilePath(
        api_path="/config/packages/ai/generated.yaml",
        relative_path="packages/ai/generated.yaml",
    )


def test_file_policy_star_glob_does_not_match_nested_paths() -> None:
    policy = FilePathPolicy(Settings(allowed_write_globs=["/config/packages/ai/*.yaml"]))

    with pytest.raises(ApiError) as exc_info:
        policy.resolve_write_path("/config/packages/ai/nested/generated.yaml")

    assert exc_info.value.code == "files.path_not_writable"


def test_file_policy_double_star_glob_matches_nested_paths() -> None:
    policy = FilePathPolicy(Settings(allowed_write_globs=["/config/packages/ai/**/*.yaml"]))

    resolved = policy.resolve_write_path("/config/packages/ai/nested/generated.yaml")

    assert resolved == ResolvedFilePath(
        api_path="/config/packages/ai/nested/generated.yaml",
        relative_path="packages/ai/nested/generated.yaml",
    )
