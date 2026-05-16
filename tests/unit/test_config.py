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
