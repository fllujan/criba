import os
from pathlib import Path

import keyring
import keyring.backend
import keyring.errors
import pytest

from tests.fixtures.build import Fixtures, build_all

# Qt sin pantalla en CI y en local.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def app_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirige las carpetas de datos de Criba a un directorio temporal."""
    monkeypatch.setenv("CRIBA_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture(scope="session")
def fx(tmp_path_factory: pytest.TempPathFactory) -> Fixtures:
    """Los PDF de prueba del spec §9 y dos exámenes, generados una vez por sesión."""
    return build_all(tmp_path_factory.mktemp("fixtures"))


class MemoryKeyring(keyring.backend.KeyringBackend):
    """Llavero en memoria: los tests nunca tocan el llavero real del sistema."""

    priority = 1  # type: ignore[assignment]

    def __init__(self) -> None:
        super().__init__()
        self.store: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.store.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.store[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        if (service, username) not in self.store:
            raise keyring.errors.PasswordDeleteError(username)
        del self.store[(service, username)]


@pytest.fixture(autouse=True)
def memory_keyring(monkeypatch: pytest.MonkeyPatch) -> MemoryKeyring:
    ring = MemoryKeyring()
    keyring.set_keyring(ring)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return ring
