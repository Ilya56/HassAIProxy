from homeassistant_proxy.config import get_settings


def test_secret_file_env_values_override_inline_env(monkeypatch, tmp_path):
    api_key_file = tmp_path / "app_api_key.txt"
    ha_token_file = tmp_path / "ha_token.txt"
    passphrase_file = tmp_path / "sftp_passphrase.txt"

    api_key_file.write_text("file-api-key\n", encoding="utf-8")
    ha_token_file.write_text("file-ha-token\n", encoding="utf-8")
    passphrase_file.write_text("file-passphrase\n", encoding="utf-8")

    monkeypatch.setenv("APP_API_KEY", "inline-api-key")
    monkeypatch.setenv("APP_API_KEY_FILE", str(api_key_file))
    monkeypatch.setenv("HA_TOKEN", "inline-ha-token")
    monkeypatch.setenv("HA_TOKEN_FILE", str(ha_token_file))
    monkeypatch.setenv("SFTP_PRIVATE_KEY_PASSPHRASE", "inline-passphrase")
    monkeypatch.setenv("SFTP_PRIVATE_KEY_PASSPHRASE_FILE", str(passphrase_file))

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.app_api_key == "file-api-key"
    assert settings.ha_token == "file-ha-token"
    assert settings.sftp_private_key_passphrase == "file-passphrase"

    get_settings.cache_clear()


def test_sentry_file_env_value_overrides_inline_env(monkeypatch, tmp_path):
    sentry_dsn_file = tmp_path / "sentry_dsn.txt"
    sentry_dsn_file.write_text("file-sentry-dsn\n", encoding="utf-8")

    monkeypatch.setenv("SENTRY_DSN", "inline-sentry-dsn")
    monkeypatch.setenv("SENTRY_DSN_FILE", str(sentry_dsn_file))
    monkeypatch.setenv("SENTRY_RELEASE", "homeassistant-proxy@0.1.0")
    monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "0.25")
    monkeypatch.setenv("SENTRY_SEND_DEFAULT_PII", "true")
    monkeypatch.setenv("SENTRY_DEBUG_ROUTE_ENABLED", "true")

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.sentry_dsn == "file-sentry-dsn"
    assert settings.sentry_release == "homeassistant-proxy@0.1.0"
    assert settings.sentry_traces_sample_rate == 0.25
    assert settings.sentry_send_default_pii is True
    assert settings.sentry_debug_route_enabled is True

    get_settings.cache_clear()
