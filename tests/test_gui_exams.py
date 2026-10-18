"""Exámenes antiguos en la interfaz (RF-09, F5)."""

from pathlib import Path

import pymupdf
import pytest
from PySide6.QtCore import QObject

from criba import settings
from criba.core import schemas
from criba.core.cache import Cache
from criba.core.errors import ErrorKind
from criba.core.llm import LLMCallError
from criba.gui.backend import Backend
from criba.gui.main_window import create_engine, load_fonts
from tests import test_gui_backend as gb
from tests.test_gui_backend import KEY, WAIT, _load, _process

pytestmark = pytest.mark.gui


@pytest.fixture
def cache(app_dirs: Path):
    with Cache(app_dirs / "cache.sqlite3") as c:
        yield c


@pytest.fixture(autouse=True)
def _close_backends(cache):  # como en test_gui_backend: antes de cerrar la caché
    yield
    while gb._OPEN:
        gb._OPEN.pop().shutdown()


@pytest.fixture
def fakes():
    return []


@pytest.fixture
def backend(qapp, cache, fakes, app_dirs):
    settings.set_api_key(KEY)
    settings.save(settings.Settings(output_dir=str(app_dirs / "out")))
    b = gb._backend(qapp, cache, fakes)
    yield b
    b.wait_idle()


def _add(qtbot, b: Backend, *pdfs: Path) -> None:
    b.addExams([p.as_uri() for p in pdfs])
    qtbot.waitUntil(lambda: not b.examsLoading, timeout=WAIT)
    qtbot.waitUntil(lambda: not b.estimating, timeout=WAIT)


def test_add_exams_before_the_book_and_they_count_in_the_estimate(qtbot, backend, fx) -> None:
    b = backend
    _add(qtbot, b, fx.examen, fx.examen_escaneado)
    assert b.examCount == 2
    assert [e["name"] for e in b.exams] == ["examen.pdf", "examen_escaneado.pdf"]
    assert b.exams[1]["scanned"] == 1
    _load(qtbot, b, fx.con_indice)
    assert b._prep is not None and len(b._prep.exams) == 2
    with_exams = b.estimateCalls
    b.removeExam(0)
    b.removeExam(0)
    qtbot.waitUntil(lambda: not b.estimating, timeout=WAIT)
    assert b.examCount == 0
    assert b.estimateCalls == with_exams - 1


def test_run_with_exam_marks_chapters(qtbot, backend, fakes, fx) -> None:
    b = backend
    _load(qtbot, b, fx.con_indice)
    _add(qtbot, b, fx.examen)
    _process(qtbot, b)
    assert b.screen == "done"
    assert len(fakes[-1].calls_for(schemas.AnalisisExamenes)) == 1
    data = next(Path(b.outlinePath).parent.glob("* - datos.json")).read_text(encoding="utf-8")
    assert '"ha_caido_en_examen": true' in data


def test_bad_exam_shows_which_file_and_keeps_the_good_ones(qtbot, backend, fx) -> None:
    b = backend
    _add(qtbot, b, fx.examen, fx.protegido)
    assert b.examCount == 1
    assert (b.examError, b.examErrorFile) == ("PASSWORD_PROTECTED", "protegido.pdf")
    assert b.error == ""  # no tapa el libro
    b.dismissExamError()
    assert b.examError == ""


def test_duplicates_and_the_book_itself_are_ignored(qtbot, backend, fx, tmp_path) -> None:
    b = backend
    _load(qtbot, b, fx.con_indice)
    copy = tmp_path / "copia.pdf"
    copy.write_bytes(fx.examen.read_bytes())
    _add(qtbot, b, fx.examen)
    _add(qtbot, b, fx.examen, copy)
    assert b.examCount == 1  # misma ruta y mismo contenido
    b.addExams([fx.con_indice.as_uri()])
    qtbot.waitUntil(lambda: not b.examsLoading, timeout=WAIT)
    assert b.examCount == 1


def test_too_many_exams(qtbot, backend, fx, tmp_path) -> None:
    b = backend
    many = []
    for i in range(b.maxExams + 1):
        p = tmp_path / f"e{i}.pdf"
        p.write_bytes(fx.examen.read_bytes())
        many.append(p.as_uri())
    b.addExams(many)
    assert b.examError == "TOO_MANY_EXAMS"
    assert b.examCount == 0


def test_exams_are_locked_while_processing_and_cleared_for_another_book(qtbot, backend, fx) -> None:
    b = backend
    _load(qtbot, b, fx.con_indice)
    _add(qtbot, b, fx.examen)
    b.start()
    b.removeExam(0)
    b.addExams([fx.examen_escaneado.as_uri()])
    assert b.examCount == 1
    qtbot.waitUntil(lambda: b.screen == "done", timeout=WAIT)
    b.processAnother()
    assert b.examCount == 0


def test_resume_brings_back_the_exams(qtbot, backend, fx) -> None:
    b = backend
    _load(qtbot, b, fx.con_indice)
    _add(qtbot, b, fx.examen)
    b.start()
    b.cancel()
    qtbot.waitUntil(lambda: b.screen == "home", timeout=WAIT)
    b.wait_idle()
    b.processAnother()
    assert b.examCount == 0 and b.resumeTitle
    b.resume()
    qtbot.waitUntil(lambda: b.hasBook and not b.loading and not b.estimating, timeout=WAIT)
    assert [e["name"] for e in b.exams] == ["examen.pdf"]


# --- QML ------------------------------------------------------------------------------


@pytest.fixture
def root(qapp, backend):
    load_fonts(qapp)
    engine = create_engine(backend)
    yield engine.rootObjects()[0]
    del engine


def test_home_offers_old_exams_link_and_lists_them(qtbot, root, backend, fx) -> None:
    link = root.findChild(QObject, "addExamsLink")
    assert link is not None and link.property("visible")
    _add(qtbot, backend, fx.examen)
    exam_list = root.findChild(QObject, "examList")
    qtbot.waitUntil(lambda: exam_list.property("count") == 1, timeout=WAIT)
    _load(qtbot, backend, fx.con_indice)
    side = root.findChild(QObject, "sideExams")
    qtbot.waitUntil(lambda: bool(side.property("visible")), timeout=WAIT)


def test_every_error_kind_has_an_interface_text() -> None:
    js = (
        Path(__file__).parent.parent / "src" / "criba" / "gui" / "qml" / "Criba" / "Messages.js"
    ).read_text(encoding="utf-8")
    missing = [k.name for k in ErrorKind if f'case "{k.name}"' not in js]
    assert missing == []


def test_book_and_exams_are_never_read_at_the_same_time(qtbot, backend, fx) -> None:
    """PyMuPDF no admite dos hilos a la vez."""
    b = backend
    b.addExams([fx.examen.as_uri()])
    b.openBook(fx.con_indice.as_uri())  # ignorado: se están leyendo exámenes
    assert not b.loading
    b.start()  # sin libro ni exámenes leídos, no empieza
    assert not b.running
    qtbot.waitUntil(lambda: not b.examsLoading, timeout=WAIT)
    b.openBook(fx.con_indice.as_uri())
    assert b.loading
    b.addExams([fx.examen_escaneado.as_uri()])  # ignorado: se está leyendo el libro
    assert not b.examsLoading
    qtbot.waitUntil(lambda: b.hasBook and not b.loading and not b.estimating, timeout=WAIT)


def test_exams_that_do_not_fit_are_refused(qtbot, backend, fx, tmp_path) -> None:
    b = backend
    big = tmp_path / "fotos.pdf"  # 21 páginas escaneadas: no caben en una llamada
    src = pymupdf.open(fx.examen_escaneado)
    out = pymupdf.open()
    for _ in range(21):
        out.insert_pdf(src)
    out.save(big)
    _add(qtbot, b, fx.examen, big)
    assert b.examCount == 1
    assert (b.examError, b.examErrorFile) == ("EXAMS_TOO_BIG", "fotos.pdf")


def test_failed_exam_analysis_is_shown_on_done(qtbot, backend, fx, monkeypatch) -> None:
    b = backend
    _load(qtbot, b, fx.con_indice)
    _add(qtbot, b, fx.examen)
    real = b._llm_factory

    def factory(key, model):
        client = real(key, model)
        client.fail = lambda r: LLMCallError("x") if r.schema is schemas.AnalisisExamenes else None
        return client

    b._llm_factory = factory
    _process(qtbot, b)
    assert b.screen == "done" and b.examsFailed
