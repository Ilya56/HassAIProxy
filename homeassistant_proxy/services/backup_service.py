from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from homeassistant_proxy.config import Settings
from homeassistant_proxy.core.errors import ApiError


class BackupService:
    def __init__(self, settings: Settings) -> None:
        self._backup_root = Path(settings.backup_root).expanduser().resolve()

    def save_backup(self, *, draft_id: str, target_path: str, content: str) -> tuple[str, str]:
        backup_id = str(uuid4())
        safe_name = target_path.removeprefix("/config/").replace("/", "__")
        backup_path = self._backup_root / draft_id / f"{backup_id}__{safe_name}"
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path.write_text(content, encoding="utf-8")
        return backup_id, backup_path.as_posix()

    def read_backup(self, backup_path: str) -> str:
        path = Path(backup_path).expanduser().resolve()
        if not path.is_relative_to(self._backup_root):
            raise ApiError(
                status_code=403,
                code="backups.path_escape",
                message="Backup path escapes the configured backup root.",
                retryable=False,
            )
        return path.read_text(encoding="utf-8")
