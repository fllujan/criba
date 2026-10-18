"""Correcciones de la revisión de código de F4 (interfaz)."""

import threading
from pathlib import Path

import pytest
from PySide6.QtCore import Q_ARG, QMetaObject, QObject, Qt

from criba import settings
from criba.core.cache import Cache
from criba.core.errors import Action, ErrorKind
from criba.core.fake_llm import FakeLLMClient
from criba.gui.backend import Backend
from criba.gui.main_window import create_engine, load_fonts
from criba.render import render_book
from tests.test_render import _libro

pytestmark = pytest.mark.gui
KEY = "sk-ant-test-0000000000000000000000000000abcd"
WAIT = 20_000
QML = Path(__file__).parent.parent / "src" / "criba" / "gui" / "qml"


@pytest.fixture
def env(qapp, app_dirs: Path):
    settings.set_api_key(KEY)
    settings.save(settings.Settings(output_dir=str(app_dirs / "out")))
    cache = Cache(app_dirs / "cache.sqlite3")
    made: list[FakeLLMClient] = []
    gate = threading.Event()
    gate.set()

    def factory(_key: str, model: str) -> FakeLLMClient:
        client = FakeLLMClient(model=model, fail=lambda _r: gate.wait(10) and None)
        made.append(client)
        return client

    backends: list[Backend] = []

    def new() -> Backend:
        b = Backend(cache, llm_factory=factory, key_checker=lambda _k, _m: None)
        backends.append(b)
        return b

    yield new, made, gate
    gate.set()
    for b in backends:
        b.shutdown()
    cache.close()


def _load(qtbot, b: Backend, pdf: Path) -> None:
    b.openBook(pdf.as_uri())
    qtbot.waitUntil(lambda: b.hasBook and not b.loading and not b.estimating, timeout=WAIT)


def test_model_change_during_replan_is_not_lost(qtbot, env, fx) -> None:
    new, made, _ = env
    b = new()
    _load(qtbot, b, fx.con_indice)
    b.level = "completo"
    b._start_replan()  # replan en marcha con el modelo anterior
    b.setModel("claude-haiku-5-5")
    qtbot.waitUntil(lambda: not b.estimating, timeout=WAIT)
    assert b._prep.model == "claude-haiku-5-5"
    b.start()
    qtbot.waitUntil(lambda: b.screen == "done", timeout=WAIT)
    assert made[-1].model == "claude-haiku-5-5"


def test_nothing_changes_the_run_while_processing(qtbot, env, fx) -> None:
    new, _, gate = env
    b = new()
    _load(qtbot, b, fx.con_indice)
    b.processAnother()  # sin procesar: vale
    _load(qtbot, b, fx.con_indice)
    gate.clear()
    b.start()
    assert b.running
    entries = b.cacheEntries
    b.changeKey()
    b.forgetKey()
    b.clearCache()
    b.processAnother()
    b.closeBook()
    b.setModel("claude-haiku-5-5")
    b.setLanguage("en")
    b.openBook(fx.sin_indice.as_uri())
    b.regenerate(1)
    assert b.screen == "processing"
    assert b.hasBook and b.fileName == fx.con_indice.name
    assert settings.get_api_key() == KEY
    assert b.model == "claude-sonnet-5-5"
    assert not b.estimating
    gate.set()
    qtbot.waitUntil(lambda: b.screen == "done", timeout=WAIT)
    assert b.cacheEntries >= entries
    assert b.historyCount == 1


def test_resume_keeps_model_and_language_and_banner_clears(qtbot, env, fx) -> None:
    new, made, gate = env
    b = new()
    _load(qtbot, b, fx.con_indice)
    gate.clear()
    b.start()
    b.cancel()
    gate.set()
    qtbot.waitUntil(lambda: b.screen == "home", timeout=WAIT)
    b.wait_idle()
    paid = sum(len(c.calls) for c in made)
    b.setModel("claude-haiku-5-5")
    b.setLanguage("en")
    assert b.resumeTitle

    b.resume()
    qtbot.waitUntil(lambda: b.hasBook and not b.loading and not b.estimating, timeout=WAIT)
    assert b.model == "claude-sonnet-5-5"  # el de entonces: lo pagado sirve
    assert b.language == ""
    b.start()
    qtbot.waitUntil(lambda: b.screen == "done", timeout=WAIT)
    assert made[-1].model == "claude-sonnet-5-5"
    assert len(made[-1].calls) < paid + 10  # no se repite lo ya pagado
    assert b.resumeTitle == ""
    assert settings.load().model == "claude-haiku-5-5"  # los ajustes no se tocan


def test_regenerate_runs_once_at_a_time(qtbot, env, fx) -> None:
    new, _, _ = env
    b = new()
    _load(qtbot, b, fx.con_indice)
    b.start()
    qtbot.waitUntil(lambda: b.screen == "done", timeout=WAIT)
    b.processAnother()
    b.refreshHistory()
    job = b.historyModel.data(b.historyModel.index(0), b.historyModel.JOB)
    for _ in range(4):
        b.regenerate(job)
    assert b.regenerating
    assert len(b._tasks) == 1
    qtbot.waitUntil(lambda: b.screen == "done", timeout=WAIT)
    assert not b.regenerating
    assert b.error == ""


def test_concurrent_renders_do_not_collide(tmp_path) -> None:
    errors: list[BaseException] = []

    def go() -> None:
        try:
            render_book(_libro(), tmp_path)
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=go) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert not list(tmp_path.glob(".*.tmp"))


def test_shutdown_waits_for_tasks_that_cannot_be_cancelled(qtbot, qapp, app_dirs) -> None:
    started = threading.Event()

    def slow_check(_k: str, _m: str) -> None:
        started.set()
        threading.Event().wait(1.5)

    with Cache(app_dirs / "c.sqlite3") as cache:
        b = Backend(cache, key_checker=slow_check)
        b.testKey(KEY)
        started.wait(5)
        b.shutdown()  # sin límite: no destruye el hilo vivo
        assert all(t.isFinished() for t in b._tasks)


def test_replan_failure_with_pending_change_replans(qtbot, env, fx, monkeypatch) -> None:
    new, _, _ = env
    b = new()
    _load(qtbot, b, fx.con_indice)
    b._replan_dirty = True
    b._replan_running = True
    b._replan_failed(RuntimeError("x"))
    qtbot.waitUntil(lambda: not b.estimating, timeout=WAIT)
    assert b.error == ""


# --- QML ------------------------------------------------------------------------------


@pytest.fixture
def ui(qapp, env):
    new, _, gate = env
    load_fonts(qapp)
    b = new()
    engine = create_engine(b)
    yield b, engine.rootObjects()[0], gate
    del engine


def _call(obj: QObject, name: str, *args: object) -> None:
    QMetaObject.invokeMethod(
        obj, name, Qt.ConnectionType.DirectConnection, *(Q_ARG("QVariant", a) for a in args)
    )


def test_every_error_action_is_handled_on_processing() -> None:
    text = (QML / "screens" / "ProcessingScreen.qml").read_text(encoding="utf-8")
    for action in Action:
        if action is not Action.CHOOSE_OTHER_FILE:  # no ocurre al procesar
            assert f'"{action.value}"' in text or action is Action.CANCEL, action


@pytest.mark.parametrize("action", ["cancelar", "esperar"])
def test_rate_limited_error_has_a_way_out(qtbot, ui, fx, action) -> None:
    b, root, _ = ui
    _load(qtbot, b, fx.con_indice)
    b._set_screen("processing")
    b._set_error(ErrorKind.RATE_LIMITED, "run")
    screen = root.findChild(QObject, "processingScreen")
    _call(screen, "act", action)
    if action == "cancelar":
        assert b.screen == "home"
        assert b.error == ""
    else:
        assert b.running or b.screen == "done"
        qtbot.waitUntil(lambda: b.screen == "done", timeout=WAIT)


def test_folder_from_settings_does_not_restart_a_failed_run(qtbot, ui, fx, tmp_path) -> None:
    b, root, _ = ui
    _load(qtbot, b, fx.con_indice)
    b._set_screen("processing")
    b._set_error(ErrorKind.OFFLINE, "run")
    _call(root, "folderChosen", (tmp_path / "otra").as_uri())  # desde Ajustes
    assert not b.running
    assert b.outputDir == str(tmp_path / "otra")

    b._set_error(ErrorKind.CANNOT_WRITE, "run")
    root.findChild(QObject, "folderDialog").setProperty("retryRun", True)  # desde el error
    _call(root, "folderChosen", (tmp_path / "buena").as_uri())
    assert b.running or b.screen == "done"
    qtbot.waitUntil(lambda: b.screen == "done", timeout=WAIT)


def test_error_with_book_loaded_is_visible(qtbot, ui, fx) -> None:
    b, root, _ = ui
    _load(qtbot, b, fx.con_indice)
    b._set_error(ErrorKind.PROCESSING_FAILED, "book")
    notice = root.findChild(QObject, "homeError")
    qtbot.waitUntil(lambda: notice.property("visible"), timeout=WAIT)


def test_nav_hidden_while_running(qtbot, ui, fx) -> None:
    b, root, gate = ui
    _load(qtbot, b, fx.con_indice)
    gate.clear()
    b.start()
    cover = root.findChild(QObject, "cover")
    assert cover.property("showNav") is False
    gate.set()
    qtbot.waitUntil(lambda: b.screen == "done", timeout=WAIT)
    assert cover.property("showNav") is True
