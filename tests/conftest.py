import os
from pathlib import Path

import pytest

# Qt sin pantalla en CI y en local.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def app_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirige las carpetas de datos de Criba a un directorio temporal."""
    monkeypatch.setenv("CRIBA_HOME", str(tmp_path))
    return tmp_path
