import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator


AppEnv = Literal["dev", "staging", "prod"]
FileBackend = Literal["local", "sftp"]


def _get_env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _get_secret_env(name: str, default: str = "") -> str:
    file_value = os.environ.get(f"{name}_FILE", "").strip()
    if not file_value:
        return _get_env(name, default)

    secret_path = Path(file_value)
    return secret_path.read_text(encoding="utf-8").strip()


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings(BaseModel):
    app_env: AppEnv = "dev"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_api_key: str = Field(default="dev-only-change-me", min_length=1)
    actor_name: str = Field(default="owner", min_length=1)
    ha_base_url: str = "http://homeassistant.local:8123"
    ha_token: str = ""
    sqlite_path: str = "./data/homeassistant_proxy.sqlite3"
    backup_root: str = "./data/backups"
    config_root: str = "/config"
    file_backend: FileBackend = "local"
    sftp_host: str = ""
    sftp_port: int = 22
    sftp_username: str = "root"
    sftp_private_key_path: str = ""
    sftp_private_key_passphrase: str = ""
    sftp_root: str = "/config"
    readonly_mode: bool = False
    allowed_write_globs: list[str] = Field(default_factory=lambda: ["/config/packages/ai/*.yaml"])
    allowed_read_globs: list[str] = Field(
        default_factory=lambda: [
            "/config/configuration.yaml",
            "/config/automations.yaml",
            "/config/scripts.yaml",
            "/config/scenes.yaml",
            "/config/climate.yaml",
            "/config/packages/ai/*.yaml",
        ]
    )
    allowed_ha_services: list[str] = Field(
        default_factory=lambda: [
            "automation.reload",
            "script.reload",
            "homeassistant.reload_all",
        ]
    )
    max_file_size_kb: int = 256
    request_timeout_seconds: float = 10.0
    ha_reload_timeout_seconds: float = 60.0

    @field_validator("allowed_write_globs", "allowed_read_globs", "allowed_ha_services", mode="before")
    @classmethod
    def parse_csv_list(cls, value: object) -> object:
        if isinstance(value, str):
            return _split_csv(value)
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings(
        app_env=_get_env("APP_ENV", "dev"),
        app_host=_get_env("APP_HOST", "127.0.0.1"),
        app_port=int(_get_env("APP_PORT", "8000")),
        app_api_key=_get_secret_env("APP_API_KEY", "dev-only-change-me"),
        actor_name=_get_env("ACTOR_NAME", "owner"),
        ha_base_url=_get_env("HA_BASE_URL", "http://homeassistant.local:8123"),
        ha_token=_get_secret_env("HA_TOKEN", ""),
        sqlite_path=_get_env("SQLITE_PATH", "./data/homeassistant_proxy.sqlite3"),
        backup_root=_get_env("BACKUP_ROOT", "./data/backups"),
        config_root=_get_env("CONFIG_ROOT", "/config"),
        file_backend=_get_env("FILE_BACKEND", "local"),
        sftp_host=_get_env("SFTP_HOST", ""),
        sftp_port=int(_get_env("SFTP_PORT", "22")),
        sftp_username=_get_env("SFTP_USERNAME", "root"),
        sftp_private_key_path=_get_env("SFTP_PRIVATE_KEY_PATH", ""),
        sftp_private_key_passphrase=_get_secret_env("SFTP_PRIVATE_KEY_PASSPHRASE", ""),
        sftp_root=_get_env("SFTP_ROOT", "/config"),
        readonly_mode=_parse_bool(_get_env("READONLY_MODE", "false")),
        allowed_write_globs=_get_env("ALLOWED_WRITE_GLOBS", "/config/packages/ai/*.yaml"),
        allowed_read_globs=_get_env(
            "ALLOWED_READ_GLOBS",
            "/config/configuration.yaml,/config/automations.yaml,/config/scripts.yaml,/config/scenes.yaml,/config/climate.yaml,/config/packages/ai/*.yaml",
        ),
        allowed_ha_services=_get_env(
            "ALLOWED_HA_SERVICES",
            "automation.reload,script.reload,homeassistant.reload_all",
        ),
        max_file_size_kb=int(_get_env("MAX_FILE_SIZE_KB", "256")),
        request_timeout_seconds=float(_get_env("REQUEST_TIMEOUT_SECONDS", "10")),
        ha_reload_timeout_seconds=float(_get_env("HA_RELOAD_TIMEOUT_SECONDS", "60")),
    )
