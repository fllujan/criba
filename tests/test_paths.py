from pathlib import Path

from criba import paths


def test_criba_home_overrides_all_dirs(app_dirs: Path) -> None:
    assert paths.data_dir() == app_dirs / "data"
    assert paths.log_dir() == app_dirs / "logs"
    assert paths.config_dir() == app_dirs / "config"
    assert paths.cache_db() == app_dirs / "data" / "cache.sqlite3"


def test_dirs_are_created(app_dirs: Path) -> None:
    assert paths.log_dir().is_dir()
    assert paths.data_dir().is_dir()


def test_default_output_dir_is_documents_criba(monkeypatch) -> None:
    monkeypatch.delenv("CRIBA_HOME", raising=False)
    out = paths.default_output_dir()
    assert out.name == "Criba"
    assert out.parent.name in {"Documents", "Documentos"} or out.parent.exists()


def test_platform_default_dirs_without_override(monkeypatch) -> None:
    monkeypatch.delenv("CRIBA_HOME", raising=False)
    assert "criba" in str(paths.data_dir(create=False)).lower()
