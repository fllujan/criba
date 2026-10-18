"""Flujo completo en la interfaz QML con la IA simulada (spec §9)."""

from pathlib import Path

import pytest
from PySide6.QtCore import QObject, QtMsgType, qInstallMessageHandler

from criba import settings
from criba.core.cache import Cache
from criba.core.fake_llm import FakeLLMClient
from criba.gui.backend import Backend
from criba.gui.main_window import create_engine, load_fonts

pytestmark = pytest.mark.gui
KEY = "sk-ant-test-0000000000000000000000000000abcd"
WAIT = 20_000


@pytest.fixture
def ui(qapp, qtbot, app_dirs: Path):
    warnings: list[str] = []

    def handler(mode, _ctx, msg) -> None:
        if mode in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg):
            warnings.append(msg)

    previous = qInstallMessageHandler(handler)
    settings.set_api_key(KEY)
    settings.save(settings.Settings(output_dir=str(app_dirs / "out")))
    load_fonts(qapp)
    cache = Cache(app_dirs / "cache.sqlite3")
    backend = Backend(
        cache,
        llm_factory=lambda _k, model: FakeLLMClient(model=model),
        key_checker=lambda _k, _m: None,
    )
    engine = create_engine(backend)
    root = engine.rootObjects()[0]
    yield backend, root, warnings
    backend.shutdown()
    del engine
    cache.close()
    qInstallMessageHandler(previous)


def _find(root: QObject, name: str) -> QObject:
    obj = root.findChild(QObject, name)
    assert obj is not None, name
    return obj


def test_load_confirm_and_reach_done(ui, qtbot, fx) -> None:
    backend, root, warnings = ui
    assert backend.screen == "home"
    backend.openBook(fx.con_indice.as_uri())
    qtbot.waitUntil(lambda: backend.hasBook and not backend.estimating, timeout=WAIT)

    generate = _find(root, "generateButton")
    qtbot.waitUntil(lambda: generate.property("enabled"), timeout=WAIT)
    generate.click()
    confirm = _find(root, "confirmStart")
    qtbot.waitUntil(lambda: confirm.property("opened"), timeout=WAIT)
    message = confirm.property("message")
    assert "páginas" in message
    assert "€" in message

    confirm.findChild(QObject, "confirmButton").click()
    qtbot.waitUntil(lambda: backend.screen == "done", timeout=WAIT)
    assert Path(backend.summaryPath).exists()
    assert Path(backend.outlinePath).exists()
    done = _find(root, "doneScreen")
    qtbot.waitUntil(lambda: done.property("visible"), timeout=WAIT)
    assert not [w for w in warnings if "qml" in w.lower()], warnings


def test_cancel_popup_cancels(ui, qtbot, fx) -> None:
    _, root, _ = ui
    confirm = _find(root, "confirmCancel")
    confirm.open()
    qtbot.waitUntil(lambda: confirm.property("opened"), timeout=WAIT)
    assert "no se vuelve a pagar" in confirm.property("message")
    confirm.close()
