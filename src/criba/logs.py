"""Logs rotativos (RNF-07) que nunca escriben claves de API (RNF-04)."""

import logging
import os
import re
from logging.handlers import RotatingFileHandler

from criba import paths

LOGGER_NAME = "criba"
MAX_BYTES = 2 * 1024 * 1024
BACKUP_COUNT = 4  # archivo activo + 4 rotados = 5 archivos
_KEY_PATTERN = re.compile(r"(sk-ant-)[A-Za-z0-9_\-]+")


def redact(text: str) -> str:
    """Oculta cualquier clave de Anthropic que aparezca en ``text``."""
    text = _KEY_PATTERN.sub(r"\1***", text)
    env_key = os.environ.get("ANTHROPIC_API_KEY")
    if env_key and len(env_key) >= 8:  # noqa: PLR2004
        text = text.replace(env_key, "***")
    return text


class _CribaFileHandler(RotatingFileHandler):
    """Handler propio, para reconocerlo entre otros (p. ej. los de pytest)."""


class _RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


def setup(level: int = logging.INFO) -> logging.Logger:
    """Configura el logger ``criba``. Llamarla varias veces no duplica handlers."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    if not any(isinstance(h, _CribaFileHandler) for h in logger.handlers):
        handler = _CribaFileHandler(
            paths.log_dir() / "criba.log",
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        handler.setFormatter(_RedactingFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
        logger.propagate = False
    return logger


def shutdown() -> None:
    """Cierra y quita los handlers (tests y salida de la app)."""
    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
