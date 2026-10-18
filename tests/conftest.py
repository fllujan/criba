import os
from pathlib import Path

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
    """Los seis PDF de prueba del spec §9, generados una vez por sesión."""
    return build_all(tmp_path_factory.mktemp("fixtures"))
