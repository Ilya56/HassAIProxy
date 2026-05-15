from __future__ import annotations

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from homeassistant_proxy.config import Settings
from homeassistant_proxy.models.api_models import ValidationCheck, ValidationResult
from homeassistant_proxy.services.file_policy import FilePathPolicy


class DraftValidationService:
    def __init__(self, settings: Settings) -> None:
        self._max_file_size_bytes = settings.max_file_size_kb * 1024
        self._yaml = YAML(typ="safe")
        self._path_policy = FilePathPolicy(settings)

    def validate_proposed_content(self, *, target_path: str, proposed_content: str) -> ValidationResult:
        checks: list[ValidationCheck] = []
        errors: list[str] = []

        path_allowed = self._path_policy.matches_write(target_path)
        checks.append(
            ValidationCheck(
                name="write_allowlist",
                ok=path_allowed,
                message="Draft target must match the configured write allowlist.",
            )
        )
        if not path_allowed:
            errors.append("Target path is outside the configured write allowlist.")

        size_ok = len(proposed_content.encode("utf-8")) <= self._max_file_size_bytes
        checks.append(
            ValidationCheck(
                name="file_size",
                ok=size_ok,
                message=f"Proposed content must be at most {self._max_file_size_bytes} bytes.",
            )
        )
        if not size_ok:
            errors.append("Proposed content exceeds the configured maximum file size.")

        yaml_valid = True
        try:
            self._yaml.load(proposed_content)
        except YAMLError:
            yaml_valid = False
            errors.append("Proposed content is not valid YAML.")
        checks.append(
            ValidationCheck(
                name="yaml_syntax",
                ok=yaml_valid,
                message="Proposed content must parse as YAML.",
            )
        )

        return ValidationResult(
            ok=path_allowed and size_ok and yaml_valid,
            yaml_valid=yaml_valid,
            path_allowed=path_allowed,
            jinja_parse_status="not_applicable",
            estimated_reload_mode="quick_reload_all",
            warnings=[],
            errors=errors,
            checks=checks,
        )
