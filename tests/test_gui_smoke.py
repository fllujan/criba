from pathlib import Path

import pytest
from PySide6.QtCore import QtMsgType, qInstallMessageHandler

from criba.core.cache import Cache
from criba.gui.backend import Backend
from criba.gui.main_window import create_engine, load_fonts

pytestmark = pytest.mark.gui


@pytest.fixture
def engine(qapp, app_dirs: Path):
    load_fonts(qapp)
    with Cache(app_dirs / "cache.sqlite3") as cache:
        backend = Backend(cache)
        eng = create_engine(backend)
        yield eng
        backend.shutdown()
        del eng


def test_main_window_loads(engine) -> None:
    roots = engine.rootObjects()
    assert roots, "QML no ha cargado"
    win = roots[0]
    assert win.property("minimumWidth") == 900
    assert win.property("minimumHeight") == 640
    assert win.property("title") == "Criba"


def test_qml_has_no_warnings(qapp, qtbot, app_dirs) -> None:
    warnings: list[str] = []

    def handler(mode, _ctx, msg) -> None:
        if mode in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg):
            warnings.append(msg)

    previous = qInstallMessageHandler(handler)
    try:
        with Cache(app_dirs / "cache.sqlite3") as cache:
            backend = Backend(cache)
            eng = create_engine(backend)
            qtbot.wait(50)
            assert eng.rootObjects()
            backend.shutdown()
            del eng
    finally:
        qInstallMessageHandler(previous)
    assert not [w for w in warnings if "qml" in w.lower()], warnings
