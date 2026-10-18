"""Backend de la interfaz con IA simulada (spec §9: tests de interfaz con pytest-qt)."""

import threading
from pathlib import Path

import pytest

from criba import logs, settings
from criba.core.cache import Cache
from criba.core.errors import CribaError, ErrorKind
from criba.core.fake_llm import FakeLLMClient
from criba.gui.backend import Backend

pytestmark = pytest.mark.gui
KEY = "sk-ant-test-0000000000000000000000000000abcd"
WAIT = 20_000


@pytest.fixture
def cache(app_dirs: Path):
    with Cache(app_dirs / "cache.sqlite3") as c:
        yield c


@pytest.fixture
def fakes():
    """Clientes simulados creados por el backend (para inspeccionarlos)."""
    return []


_OPEN: list[Backend] = []


@pytest.fixture(autouse=True)
def _close_backends(cache):  # depende de la caché: se cierra antes que ella
    """Cierra cada backend al terminar: destruir un QThread vivo aborta Qt (en Windows, siempre)."""
    yield
    while _OPEN:
        _OPEN.pop().shutdown()


def _backend(qapp, cache, fakes, *, fail=None, checker=None) -> Backend:
    def factory(key: str, model: str) -> FakeLLMClient:
        assert key == KEY
        client = FakeLLMClient(model=model, fail=fail)
        fakes.append(client)
        return client

    def ok_checker(key: str, model: str) -> None:
        return None

    backend = Backend(cache, llm_factory=factory, key_checker=checker or ok_checker)
    _OPEN.append(backend)
    return backend


@pytest.fixture
def backend(qapp, cache, fakes, app_dirs):
    settings.set_api_key(KEY)
    settings.save(settings.Settings(output_dir=str(app_dirs / "out")))
    b = _backend(qapp, cache, fakes)
    yield b
    b.wait_idle()


def _load(qtbot, b: Backend, pdf: Path) -> None:
    b.openBook(pdf.as_uri())
    qtbot.waitUntil(lambda: not b.loading and (b.hasBook or bool(b.error)), timeout=WAIT)
    qtbot.waitUntil(lambda: not b.estimating, timeout=WAIT)


def _process(qtbot, b: Backend) -> None:
    b.start()
    qtbot.waitUntil(lambda: b.screen != "processing", timeout=WAIT)


# --- Clave ------------------------------------------------------------------------


def test_first_run_without_key_opens_setup(qapp, cache, fakes, app_dirs) -> None:
    b = _backend(qapp, cache, fakes)
    assert b.screen == "setup"
    assert not b.hasKey


def test_valid_key_is_saved_in_keyring_and_goes_home(qtbot, qapp, cache, fakes, app_dirs) -> None:
    seen = []
    b = _backend(qapp, cache, fakes, checker=lambda k, m: seen.append((k, m)))
    b.testKey(f"  {KEY}\n")
    assert b.keyStatus == "checking"
    qtbot.waitUntil(lambda: b.keyStatus == "ok", timeout=WAIT)
    assert seen == [(KEY, "claude-sonnet-5-5")]
    assert settings.get_api_key() == KEY
    assert b.screen == "home"
    assert b.hasKey
    assert b.keyHint == "…abcd"


def test_invalid_key_shows_error_and_is_not_saved(qtbot, qapp, cache, fakes, app_dirs) -> None:
    def bad(_k: str, _m: str) -> None:
        raise CribaError(ErrorKind.INVALID_KEY, "401")

    b = _backend(qapp, cache, fakes, checker=bad)
    b.testKey(KEY)
    qtbot.waitUntil(lambda: b.keyStatus == "error", timeout=WAIT)
    assert b.keyError == "INVALID_KEY"
    assert settings.get_api_key() is None
    assert b.screen == "setup"


def test_empty_key_is_rejected_without_calling(qtbot, qapp, cache, fakes, app_dirs) -> None:
    b = _backend(qapp, cache, fakes, checker=lambda k, m: pytest.fail("no debe llamar"))
    b.testKey("   ")
    assert b.keyStatus == "error"


def test_offline_key_check_is_reported(qtbot, qapp, cache, fakes, app_dirs) -> None:
    def offline(_k: str, _m: str) -> None:
        raise CribaError(ErrorKind.OFFLINE)

    b = _backend(qapp, cache, fakes, checker=offline)
    b.testKey(KEY)
    qtbot.waitUntil(lambda: b.keyStatus == "error", timeout=WAIT)
    assert b.keyError == "OFFLINE"


def test_change_and_forget_key(qtbot, backend) -> None:
    assert backend.screen == "home"
    backend.changeKey()
    assert backend.screen == "setup"
    backend.cancelKeyChange()
    assert backend.screen == "home"
    backend.forgetKey()
    assert settings.get_api_key() is None
    assert backend.screen == "setup"


# --- Libro y estimación ----------------------------------------------------------------


def test_open_book_shows_chapters_and_estimate(qtbot, backend, fx) -> None:
    _load(qtbot, backend, fx.con_indice)
    assert backend.hasBook
    assert backend.fileName == fx.con_indice.name
    assert backend.pageCount == 25
    assert backend.subject
    assert backend.chapterModel.rowCount() == 4
    assert backend.chapterSource == "toc"
    assert backend.estimateCalls > 0
    assert backend.estimateEur > 0
    assert 0 < backend.estimateEur < backend.estimateUsd
    assert backend.estimateSeconds > 0
    assert backend.selectedPages == 25
    assert backend.selectedChapters[1] == {
        "title": "Capítulo 1. La célula",
        "firstPage": 2,
        "lastPage": 9,
    }
    assert backend.screen == "home"


def test_unchecking_chapters_lowers_estimate(qtbot, backend, fx) -> None:
    _load(qtbot, backend, fx.con_indice)
    full = backend.estimateEur
    backend.setChapterChecked(2, False)
    backend.setChapterChecked(3, False)
    assert (backend.checkedCount, backend.chapterCount) == (2, 4)
    assert backend.estimating
    qtbot.waitUntil(lambda: not backend.estimating, timeout=WAIT)
    assert 0 < backend.estimateEur < full
    assert backend.selectedPages == 1 + 8
    backend.setAllChapters(True)
    qtbot.waitUntil(lambda: not backend.estimating, timeout=WAIT)
    assert backend.estimateEur == pytest.approx(full)


def test_level_and_page_range_change_estimate(qtbot, backend, fx) -> None:
    _load(qtbot, backend, fx.con_indice)
    normal = backend.estimateEur
    backend.level = "completo"
    qtbot.waitUntil(lambda: not backend.estimating, timeout=WAIT)
    assert backend.estimateEur > normal
    backend.level = "nada"  # se ignora
    assert backend.level == "completo"
    backend.setPageRange(30, 5)  # se ordena y se recorta al libro
    assert (backend.pageFrom, backend.pageTo) == (5, 25)
    qtbot.waitUntil(lambda: not backend.estimating, timeout=WAIT)
    assert backend.selectedPages == 21
    backend.setPageRange(0, 0)
    assert (backend.pageFrom, backend.pageTo) == (0, 0)


def test_scanned_pages_are_counted(qtbot, backend, fx) -> None:
    _load(qtbot, backend, fx.escaneado)
    assert backend.scannedPages == 5


@pytest.mark.parametrize(
    ("name", "kind"),
    [("protegido", "PASSWORD_PROTECTED"), ("danado", "CORRUPT")],
)
def test_bad_pdf_shows_friendly_error(qtbot, backend, fx, name, kind) -> None:
    _load(qtbot, backend, getattr(fx, name))
    assert not backend.hasBook
    assert backend.error == kind
    assert backend.errorWhere == "book"
    assert backend.errorActions == ["elegir_otro_archivo"]
    backend.dismissError()
    assert backend.error == ""


def test_missing_file(qtbot, backend, tmp_path) -> None:
    _load(qtbot, backend, tmp_path / "no-existe.pdf")
    assert backend.error == "NOT_FOUND"


def test_close_book(qtbot, backend, fx) -> None:
    _load(qtbot, backend, fx.con_indice)
    backend.closeBook()
    assert not backend.hasBook
    assert backend.chapterModel.rowCount() == 0


# --- Procesar ---------------------------------------------------------------------------


def test_full_flow_reaches_done_with_both_pdfs(qtbot, backend, fx, fakes) -> None:
    """Spec §9: cargar un PDF, confirmar y llegar a Listo con el cliente simulado."""
    _load(qtbot, backend, fx.con_indice)
    backend.subject = "Biología 1.º"
    stages: list[str] = []
    backend.progressChanged.connect(lambda: stages.append(backend.stage))
    _process(qtbot, backend)
    assert backend.screen == "done", backend.error
    assert Path(backend.summaryPath).name == "Biología 1.º - Resumen.pdf"
    assert Path(backend.outlinePath).exists()
    assert backend.fraction == 1.0
    assert backend.resultCostEur > 0
    assert backend.failedPages == ""
    assert {"analizando", "sintetizando", "generando"} <= set(stages)
    assert backend.historyCount == 1
    assert len(fakes) == 1


def test_second_run_is_free(qtbot, backend, fx, fakes) -> None:
    _load(qtbot, backend, fx.con_indice)
    _process(qtbot, backend)
    backend.processAnother()
    assert not backend.hasBook
    _load(qtbot, backend, fx.con_indice)
    assert backend.estimateCachedCalls == backend.estimateCalls
    assert backend.estimateEur == 0
    _process(qtbot, backend)
    assert backend.screen == "done"
    assert fakes[1].calls == []


def test_run_error_is_friendly_and_keeps_book(qtbot, qapp, cache, fakes, app_dirs, fx) -> None:
    settings.set_api_key(KEY)

    def fail(_req):
        return CribaError(ErrorKind.NO_CREDIT, "credit balance")

    b = _backend(qapp, cache, fakes, fail=fail)
    _load(qtbot, b, fx.con_indice)
    b.start()
    qtbot.waitUntil(lambda: bool(b.error), timeout=WAIT)
    b.wait_idle()
    assert b.error == "NO_CREDIT"
    assert b.errorWhere == "run"
    assert b.errorActions == ["abrir_consola", "reintentar"]
    assert b.screen == "processing"
    b.backToHome()
    assert b.screen == "home"
    assert b.hasBook


def test_cancel_returns_home_and_offers_resume(qtbot, qapp, cache, fakes, app_dirs, fx) -> None:
    settings.set_api_key(KEY)
    gate = threading.Event()

    def slow(_req):
        gate.wait(5)

    b = _backend(qapp, cache, fakes, fail=slow)
    _load(qtbot, b, fx.con_indice)
    b.start()
    assert b.screen == "processing"
    b.cancel()
    assert b.cancelling
    gate.set()
    qtbot.waitUntil(lambda: b.screen == "home", timeout=WAIT)
    b.wait_idle()
    assert b.notice == "cancelled"
    assert b.hasBook
    assert b.resumeTitle

    fresh = _backend(qapp, cache, fakes)  # al volver a abrir la app
    assert fresh.resumeTitle
    fresh.resume()
    qtbot.waitUntil(lambda: fresh.hasBook and not fresh.estimating, timeout=WAIT)
    assert fresh.fileName == fx.con_indice.name
    fresh.wait_idle()


def test_start_without_key_opens_setup(qtbot, backend, fx) -> None:
    _load(qtbot, backend, fx.con_indice)
    settings.delete_api_key()
    backend.start()
    assert backend.screen == "setup"
    assert backend.error == "NO_KEY"


def test_cannot_write_output_offers_other_folder(qtbot, backend, fx, tmp_path) -> None:
    blocker = tmp_path / "archivo"
    blocker.write_text("x")
    backend.setOutputDir(str(blocker / "sub"))
    _load(qtbot, backend, fx.con_indice)
    backend.start()
    qtbot.waitUntil(lambda: bool(backend.error), timeout=WAIT)
    backend.wait_idle()
    assert backend.error == "CANNOT_WRITE"
    assert backend.errorActions == ["elegir_otra_carpeta"]
    backend.setOutputDir(str(tmp_path / "bien"))
    assert backend.error == ""


# --- Historial y ajustes -----------------------------------------------------------------


def test_regenerate_from_history_is_free(qtbot, backend, fx, fakes) -> None:
    _load(qtbot, backend, fx.con_indice)
    _process(qtbot, backend)
    summary = Path(backend.summaryPath)
    summary.unlink()
    backend.processAnother()
    backend.refreshHistory()
    model = backend.historyModel
    job_id = model.data(model.index(0), model.JOB)
    assert model.data(model.index(0), model.AVAILABLE) is False
    backend.regenerate(job_id)
    qtbot.waitUntil(lambda: backend.screen == "done", timeout=WAIT)
    assert summary.exists()
    assert len(fakes) == 1


def test_regenerate_unknown_job(qtbot, backend) -> None:
    backend.regenerate(999)
    assert backend.error == "NOT_FOUND"


def test_settings_are_persisted(qtbot, backend, tmp_path) -> None:
    backend.setModel("claude-haiku-5-5")
    backend.setModel("gpt-0")  # se ignora
    backend.setLanguage("en")
    backend.setOutputDir((tmp_path / "pdfs").as_uri())
    saved = settings.load()
    assert saved.model == "claude-haiku-5-5"
    assert saved.language == "en"
    assert saved.output_dir == str(tmp_path / "pdfs")
    assert backend.outputDir == str(tmp_path / "pdfs")
    backend.setLanguage("")
    assert settings.load().language is None
    assert "claude-sonnet-5-5" in backend.models
    assert "es" in backend.languages


def test_model_change_updates_loaded_book(qtbot, backend, fx) -> None:
    _load(qtbot, backend, fx.con_indice)
    sonnet = backend.estimateEur
    backend.setModel("claude-haiku-5-5")
    qtbot.waitUntil(lambda: not backend.estimating, timeout=WAIT)
    assert backend.estimateEur < sonnet


def test_clear_cache(qtbot, backend, fx) -> None:
    _load(qtbot, backend, fx.con_indice)
    _process(qtbot, backend)
    assert backend.cacheEntries > 0
    backend.clearCache()
    assert backend.cacheEntries == 0


def test_api_key_never_logged(qtbot, backend, fx, app_dirs) -> None:
    logs.setup()
    backend.testKey(KEY)
    qtbot.waitUntil(lambda: backend.keyStatus == "ok", timeout=WAIT)
    _load(qtbot, backend, fx.con_indice)
    _process(qtbot, backend)
    logs.shutdown()
    for f in app_dirs.rglob("*"):
        if f.is_file():
            assert KEY.encode() not in f.read_bytes(), f


def test_shutdown_cancels_running_job(qtbot, qapp, cache, fakes, app_dirs, fx) -> None:
    settings.set_api_key(KEY)
    gate = threading.Event()
    b = _backend(qapp, cache, fakes, fail=lambda _r: gate.wait(5) and None)
    _load(qtbot, b, fx.con_indice)
    b.start()
    gate.set()
    b.shutdown()
    assert not b._tasks or all(t.isFinished() for t in b._tasks)
