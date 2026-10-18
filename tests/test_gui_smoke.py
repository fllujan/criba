import pytest
from PySide6.QtCore import QtMsgType, qInstallMessageHandler

from criba.gui.main_window import create_engine

pytestmark = pytest.mark.gui


def test_main_window_loads(qapp) -> None:
    engine = create_engine()
    roots = engine.rootObjects()
    assert roots, "QML no ha cargado"
    win = roots[0]
    assert win.property("minimumWidth") == 900
    assert win.property("minimumHeight") == 640
    assert win.property("title") == "Criba"


def test_qml_has_no_warnings(qapp, qtbot) -> None:
    warnings: list[str] = []

    def handler(mode, _ctx, msg) -> None:
        if mode in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg):
            warnings.append(msg)

    previous = qInstallMessageHandler(handler)
    try:
        engine = create_engine()
        qtbot.wait(50)
        assert engine.rootObjects()
    finally:
        qInstallMessageHandler(previous)
    assert not [w for w in warnings if "qml" in w.lower()], warnings
