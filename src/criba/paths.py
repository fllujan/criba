"""Rutas de datos, logs, ajustes y salida, correctas en macOS y Windows.

La variable de entorno ``CRIBA_HOME`` redirige todas las carpetas internas
(útil en tests y para una instalación portátil).
"""

import os
from pathlib import Path

import platformdirs

APP_NAME = "Criba"


def _base(kind: str) -> Path:
    override = os.environ.get("CRIBA_HOME")
    if override:
        return Path(override) / kind
    match kind:
        case "data":
            return platformdirs.user_data_path(APP_NAME, appauthor=False)
        case "logs":
            return platformdirs.user_log_path(APP_NAME, appauthor=False)
        case "config":
            return platformdirs.user_config_path(APP_NAME, appauthor=False)
    raise ValueError(kind)


def _ensure(path: Path, create: bool) -> Path:
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def data_dir(*, create: bool = True) -> Path:
    """Carpeta de datos de la app (caché, historial)."""
    return _ensure(_base("data"), create)


def log_dir(*, create: bool = True) -> Path:
    """Carpeta de logs rotativos (RNF-07)."""
    return _ensure(_base("logs"), create)


def config_dir(*, create: bool = True) -> Path:
    """Carpeta del archivo de ajustes JSON."""
    return _ensure(_base("config"), create)


def cache_db() -> Path:
    """Ruta de la base SQLite de la caché."""
    return data_dir() / "cache.sqlite3"


def default_output_dir() -> Path:
    """Carpeta de salida por defecto: Documentos/Criba (con ``CRIBA_HOME``, dentro de ella)."""
    override = os.environ.get("CRIBA_HOME")
    if override:  # tests y scripts: nunca escriben en los Documentos reales
        return Path(override) / "out"
    return platformdirs.user_documents_path() / APP_NAME
