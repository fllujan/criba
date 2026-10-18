import json

import keyring.errors

from criba import settings


def test_defaults_when_missing(app_dirs) -> None:
    s = settings.load()
    assert s.model == "claude-sonnet-5-5"
    assert s.output_dir is None and s.language is None
    assert s.output_path == app_dirs / "out"  # con CRIBA_HOME, nunca en los Documentos reales


def test_save_and_load_roundtrip(app_dirs, tmp_path) -> None:
    settings.save(
        settings.Settings(model="claude-haiku-5-5", output_dir=str(tmp_path), language="en")
    )
    s = settings.load()
    assert (s.model, s.output_dir, s.language) == ("claude-haiku-5-5", str(tmp_path), "en")
    assert s.output_path == tmp_path


def test_corrupt_or_unknown_values_fall_back(app_dirs) -> None:
    settings.settings_file().write_text("{no es json", encoding="utf-8")
    assert settings.load().model == "claude-sonnet-5-5"
    settings.settings_file().write_text(json.dumps({"model": "gpt-9", "output_dir": 3}))
    s = settings.load()
    assert s.model == "claude-sonnet-5-5" and s.output_dir is None


def test_api_key_never_in_settings_file(app_dirs, memory_keyring) -> None:
    settings.set_api_key("  sk-ant-secreta-123  ")
    settings.save(settings.Settings())
    assert "sk-ant" not in settings.settings_file().read_text(encoding="utf-8")
    assert memory_keyring.store[("Criba", "anthropic_api_key")] == "sk-ant-secreta-123"


def test_api_key_from_keyring_and_env_priority(monkeypatch) -> None:
    assert settings.get_api_key() is None
    settings.set_api_key("sk-ant-llavero")
    assert settings.get_api_key() == "sk-ant-llavero"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-entorno")
    assert settings.get_api_key() == "sk-ant-entorno"


def test_delete_api_key_idempotent() -> None:
    settings.set_api_key("x")
    settings.delete_api_key()
    settings.delete_api_key()
    assert settings.get_api_key() is None


def test_keyring_failure_returns_none(monkeypatch) -> None:
    def boom(*_):
        raise keyring.errors.KeyringError("sin llavero")

    monkeypatch.setattr(settings.keyring, "get_password", boom)
    assert settings.get_api_key() is None
