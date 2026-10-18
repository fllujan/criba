import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from criba import logs

FAKE_KEY = "sk-ant-api03-" + "x" * 40


@pytest.fixture(autouse=True)
def _reset_logging():
    yield
    logs.shutdown()


def test_rotating_handler_5_files_of_2mb(app_dirs: Path) -> None:
    logs.setup()
    handlers = [
        h for h in logging.getLogger("criba").handlers if isinstance(h, RotatingFileHandler)
    ]
    assert len(handlers) == 1
    assert handlers[0].maxBytes == 2 * 1024 * 1024
    assert handlers[0].backupCount == 4  # 1 activo + 4 rotados = 5 archivos


def test_setup_is_idempotent(app_dirs: Path) -> None:
    logs.setup()
    logs.setup()
    handlers = logging.getLogger("criba").handlers
    assert sum(isinstance(h, RotatingFileHandler) for h in handlers) == 1


def test_api_key_never_reaches_log_file(app_dirs: Path) -> None:
    logs.setup()
    log = logging.getLogger("criba.test")
    log.error("fallo con clave %s", FAKE_KEY)
    log.error(f"en mensaje directo {FAKE_KEY}")
    try:
        raise RuntimeError(f"Authorization: Bearer {FAKE_KEY}")
    except RuntimeError:
        log.exception("excepción")
    logs.shutdown()
    text = (app_dirs / "logs" / "criba.log").read_text(encoding="utf-8")
    assert "sk-ant-" in text  # se ve que había una clave…
    assert "x" * 40 not in text  # …pero nunca su valor


def test_redact_handles_env_key(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "clave-rara-sin-prefijo-123456")
    assert "clave-rara" not in logs.redact("valor clave-rara-sin-prefijo-123456")
