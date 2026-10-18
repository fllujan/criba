"""Ajustes de la app (RF-17) y clave de API (RNF-04).

Los ajustes van en un JSON en la carpeta de configuración. La clave de API
**nunca** se escribe en archivos: se guarda en el llavero del sistema (Llavero de
macOS, Administrador de credenciales de Windows). En desarrollo se puede usar la
variable de entorno ``ANTHROPIC_API_KEY``, que tiene prioridad.
"""

import contextlib
import json
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path

import keyring
import keyring.errors

from criba import paths
from criba.core.cost import DEFAULT_MODEL, PRICES

log = logging.getLogger(__name__)

KEYRING_SERVICE = "Criba"
KEYRING_USER = "anthropic_api_key"
ENV_KEY = "ANTHROPIC_API_KEY"


@dataclass(slots=True)
class Settings:
    """Ajustes editables en la pantalla de Ajustes."""

    model: str = DEFAULT_MODEL
    output_dir: str | None = None  # None = Documentos/Criba
    language: str | None = None  # None = el idioma del libro

    @property
    def output_path(self) -> Path:
        """Carpeta de salida efectiva."""
        return Path(self.output_dir) if self.output_dir else paths.default_output_dir()


def settings_file() -> Path:
    """Ruta del archivo de ajustes."""
    return paths.config_dir() / "settings.json"


def load() -> Settings:
    """Lee los ajustes; si faltan o están dañados, usa los valores por defecto."""
    try:
        data = json.loads(settings_file().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return Settings()
    except (OSError, ValueError):
        log.warning("Ajustes dañados; se usan los valores por defecto")
        return Settings()
    s = Settings()
    if data.get("model") in PRICES:
        s.model = data["model"]
    if isinstance(data.get("output_dir"), str):
        s.output_dir = data["output_dir"]
    if isinstance(data.get("language"), str):
        s.language = data["language"]
    return s


def save(settings: Settings) -> None:
    """Guarda los ajustes (sin la clave de API)."""
    path = settings_file()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def get_api_key() -> str | None:
    """Clave de API: variable de entorno o llavero del sistema."""
    env = os.environ.get(ENV_KEY, "").strip()
    if env:
        return env
    try:
        return keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
    except keyring.errors.KeyringError:
        log.warning("No se puede leer el llavero del sistema")
        return None


def set_api_key(key: str) -> None:
    """Guarda la clave en el llavero del sistema."""
    keyring.set_password(KEYRING_SERVICE, KEYRING_USER, key.strip())


def delete_api_key() -> None:
    """Borra la clave del llavero (si estaba)."""
    with contextlib.suppress(keyring.errors.PasswordDeleteError):
        keyring.delete_password(KEYRING_SERVICE, KEYRING_USER)
