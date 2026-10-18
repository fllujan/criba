"""Puente entre QML y el núcleo: estado de la app, acciones y trabajo en segundo plano.

QML solo lee propiedades y llama a slots; todo lo pesado corre en ``worker.Task``.
Los textos visibles los pone QML con ``qsTr``: aquí solo viajan datos y claves
(por ejemplo, el nombre de un ``ErrorKind``).
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    Property,
    QCoreApplication,
    QObject,
    Qt,
    QThread,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QDesktopServices

from criba import paths, settings
from criba.core import ingest
from criba.core.analyze import LANGUAGE_NAMES
from criba.core.cache import Cache
from criba.core.cost import PRICES, to_eur
from criba.core.errors import Cancelled, CribaError, ErrorKind
from criba.core.exams import MAX_EXAMS, Exam, limits_problem, read_exam
from criba.core.llm import AnthropicClient, LLMClient, check_api_key
from criba.core.pipeline import (
    CancelToken,
    Options,
    Prepared,
    Progress,
    RunResult,
    Stage,
    overall_fraction,
    prepare,
    replan,
    run,
)
from criba.core.schemas import Libro
from criba.gui.models import ChapterModel, ChapterRow, HistoryModel, HistoryRow
from criba.gui.worker import Report, Task
from criba.render import render_book

log = logging.getLogger(__name__)

LlmFactory = Callable[[str, str], LLMClient]  # (clave, modelo) → cliente
KeyChecker = Callable[[str, str], None]  # lanza CribaError si la clave no vale
CONSOLE_URL = "https://console.anthropic.com/settings/billing"
REPLAN_DELAY_MS = 150
KEY_HINT_MIN = 12  # solo se enseñan los 4 últimos caracteres de una clave larga
NIVELES = ("esencial", "normal", "completo")
TIPOS = ("test", "desarrollo", "mixto")


@dataclass(frozen=True, slots=True)
class Done:
    """Lo que enseña la pantalla Listo."""

    summary: Path
    outline: Path
    cost_usd: float
    failed_pages: list[tuple[int, int]]
    exams_failed: bool = False


def _error_kind(exc: BaseException) -> ErrorKind:
    if isinstance(exc, CribaError):
        return exc.kind
    log.error("Error inesperado", exc_info=exc)
    return ErrorKind.PROCESSING_FAILED


def _read_exams(paths: list[Path]) -> tuple[list[Exam], tuple[str, ErrorKind] | None]:
    """Lee los exámenes que se puedan; del primero que falle, su nombre y el motivo."""
    found: dict[str, Exam] = {}
    problem: tuple[str, ErrorKind] | None = None
    for path in paths:
        try:
            exam = read_exam(path)
            found.setdefault(exam.sha256, exam)
        except CribaError as exc:
            log.info("Examen no válido %s: %s (%s)", path.name, exc.kind.name, exc.detail)
            problem = problem or (path.name, exc.kind)
    return list(found.values()), problem


def _local_path(url_or_path: str) -> Path:
    url = QUrl(url_or_path)
    return Path(url.toLocalFile()) if url.isLocalFile() else Path(url_or_path)


class Backend(QObject):
    """Estado que ve QML. Pantallas: ``setup``, ``home``, ``processing``, ``done``."""

    screenChanged = Signal()
    keyChanged = Signal()
    bookChanged = Signal()
    estimateChanged = Signal()
    progressChanged = Signal()
    resultChanged = Signal()
    errorChanged = Signal()
    settingsChanged = Signal()
    historyChanged = Signal()
    noticeChanged = Signal()
    selectionChanged = Signal()
    examsChanged = Signal()

    def __init__(
        self,
        cache: Cache,
        *,
        llm_factory: LlmFactory = AnthropicClient,
        key_checker: KeyChecker = check_api_key,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._cache = cache
        self._llm_factory = llm_factory
        self._key_checker = key_checker
        self._settings = settings.load()
        self._tasks: set[Task] = set()

        self._key_status = ""  # "", "checking", "ok", "error"
        self._key_error = ""
        self._has_key = settings.get_api_key() is not None
        self._screen = "home" if self._has_key else "setup"

        self._loading = False
        self._load_fraction = 0.0
        # «Continuar donde lo dejaste» usa el modelo e idioma de entonces (la caché va con ellos).
        self._book_model: str | None = None
        self._book_language: tuple[str | None] | None = None
        self._regenerating = False
        self._prep: Prepared | None = None
        self._subject = ""
        self._level = "normal"
        self._exam = "mixto"
        self._page_from = 0
        self._page_to = 0
        # Exámenes antiguos (RF-09): se leen al añadirlos; los errores van aparte.
        self._exams: list[Exam] = []
        self._exams_loading = False
        self._exam_error = ""  # nombre del ErrorKind
        self._exam_error_file = ""
        self.chapters = ChapterModel(self)
        self.chapters.selectionChanged.connect(self._schedule_replan)
        self.chapters.selectionChanged.connect(self.selectionChanged)

        self._estimating = False
        self._replan_running = False
        self._replan_dirty = False
        self._replan_timer = QTimer(self)
        self._replan_timer.setSingleShot(True)
        self._replan_timer.setInterval(REPLAN_DELAY_MS)
        self._replan_timer.timeout.connect(self._start_replan)

        self._progress: Progress | None = None
        self._fraction = 0.0
        self._cancel: CancelToken | None = None
        self._cancelling = False

        self._done: Done | None = None
        self._error = ""  # nombre del ErrorKind
        self._error_where = ""  # "book", "run", "key", "history"
        self._notice = ""  # "cancelled", "rate_limited"…

        self.history = HistoryModel(self)
        self._resume: dict[str, Any] | None = None
        self.refreshHistory()

    # --- Utilidades ---------------------------------------------------------------

    def _spawn(
        self,
        job: Callable[[Report], object],
        on_ok: Callable[[Any], None],
        on_fail: Callable[[BaseException], None],
        on_progress: Callable[[Any], None] | None = None,
    ) -> Task:
        task = Task(job, self)
        # En cola: los callbacks se ejecutan en el hilo de la interfaz (el del Task), nunca
        # en el del trabajo, aunque sean lambdas sin objeto receptor.
        queued = Qt.ConnectionType.QueuedConnection
        task.succeeded.connect(on_ok, queued)
        task.failed.connect(on_fail, queued)
        if on_progress:
            task.progressed.connect(on_progress, queued)
        task.finished.connect(lambda: self._reap(task), queued)
        self._tasks.add(task)
        task.start()
        return task

    def _reap(self, task: Task) -> None:
        assert QThread.currentThread() is self.thread()  # noqa: S101 (invariante de hilos)
        self._tasks.discard(task)
        task.deleteLater()

    def shutdown(self) -> None:
        """Al cerrar la ventana: cancela lo que esté en marcha (queda en la caché) y espera."""
        if self._cancel is not None:
            self._cancel.cancel()
        self.wait_idle()

    def wait_idle(self) -> None:
        """Espera a que terminen los hilos y entrega sus resultados (al cerrar y en tests).

        Sin límite de tiempo: destruir un QThread vivo aborta la app. Lo único largo
        (procesar) ya se ha cancelado; leer un libro o comprobar la clave acaban solos.
        """
        for task in list(self._tasks):
            task.wait()
        QCoreApplication.sendPostedEvents()
        QCoreApplication.processEvents()

    def _set_screen(self, screen: str) -> None:
        if screen != self._screen:
            self._screen = screen
            self.screenChanged.emit()

    def _set_error(self, kind: ErrorKind | None, where: str = "") -> None:
        self._error = kind.name if kind else ""
        self._error_where = where if kind else ""
        self.errorChanged.emit()

    def _set_notice(self, notice: str) -> None:
        if notice != self._notice:
            self._notice = notice
            self.noticeChanged.emit()

    def _model(self) -> str:
        return self._book_model or self._settings.model

    def _language(self) -> str | None:
        return self._book_language[0] if self._book_language else self._settings.language

    def _busy(self) -> bool:
        """Hay un procesado en marcha: no se cambia nada que le afecte."""
        if self._cancel is not None:
            log.info("Acción ignorada: hay un procesado en marcha")
            return True
        return False

    def _options(self) -> Options:
        checked = self.chapters.checked_indices()
        all_checked = len(checked) == len(self.chapters)
        page_range = None
        if self._page_from and self._page_to and self._page_from <= self._page_to:
            page_range = (self._page_from, self._page_to)
        return Options(
            asignatura=self._subject.strip() or "Criba",
            nivel=self._level,  # type: ignore[arg-type]
            tipo_examen=self._exam,  # type: ignore[arg-type]
            idioma=self._language(),
            chapters=None if all_checked else tuple(checked),
            page_range=page_range,
            output_dir=self._settings.output_path,
            exams=tuple(e.path for e in self._exams),
        )

    # --- Propiedades ----------------------------------------------------------------

    def _get_screen(self) -> str:
        return self._screen

    screen = Property(str, _get_screen, notify=screenChanged)

    def _get_has_key(self) -> bool:
        return self._has_key

    hasKey = Property(bool, _get_has_key, notify=keyChanged)

    def _get_key_hint(self) -> str:
        key = settings.get_api_key() if self._has_key else None
        return f"…{key[-4:]}" if key and len(key) > KEY_HINT_MIN else ""

    keyHint = Property(str, _get_key_hint, notify=keyChanged)

    def _get_key_status(self) -> str:
        return self._key_status

    keyStatus = Property(str, _get_key_status, notify=keyChanged)

    def _get_key_error(self) -> str:
        return self._key_error

    keyError = Property(str, _get_key_error, notify=keyChanged)

    def _get_loading(self) -> bool:
        return self._loading

    loading = Property(bool, _get_loading, notify=bookChanged)

    def _get_load_fraction(self) -> float:
        return self._load_fraction

    loadFraction = Property(float, _get_load_fraction, notify=bookChanged)

    def _get_has_book(self) -> bool:
        return self._prep is not None

    hasBook = Property(bool, _get_has_book, notify=bookChanged)

    def _get_file_name(self) -> str:
        return self._prep.book.info.path.name if self._prep else ""

    fileName = Property(str, _get_file_name, notify=bookChanged)

    def _get_page_count(self) -> int:
        return self._prep.book.info.page_count if self._prep else 0

    pageCount = Property(int, _get_page_count, notify=bookChanged)

    def _get_chapter_source(self) -> str:
        return self._prep.chapters[0].source if self._prep and self._prep.chapters else ""

    chapterSource = Property(str, _get_chapter_source, notify=bookChanged)

    def _get_chapters(self) -> ChapterModel:
        return self.chapters

    chapterModel = Property(QObject, _get_chapters, constant=True)

    def _get_checked_count(self) -> int:
        return len(self.chapters.checked_indices())

    checkedCount = Property(int, _get_checked_count, notify=selectionChanged)

    def _get_chapter_count(self) -> int:
        return len(self.chapters)

    chapterCount = Property(int, _get_chapter_count, notify=selectionChanged)

    def _get_subject(self) -> str:
        return self._subject

    def _set_subject(self, value: str) -> None:
        if value != self._subject:
            self._subject = value
            self.bookChanged.emit()

    subject = Property(str, _get_subject, _set_subject, notify=bookChanged)

    def _get_level(self) -> str:
        return self._level

    def _set_level(self, value: str) -> None:
        if value in NIVELES and value != self._level:
            self._level = value
            self.bookChanged.emit()
            self._schedule_replan()

    level = Property(str, _get_level, _set_level, notify=bookChanged)

    def _get_exam(self) -> str:
        return self._exam

    def _set_exam(self, value: str) -> None:
        if value in TIPOS and value != self._exam:
            self._exam = value
            self.bookChanged.emit()
            self._schedule_replan()

    examType = Property(str, _get_exam, _set_exam, notify=bookChanged)

    def _get_page_from(self) -> int:
        return self._page_from

    pageFrom = Property(int, _get_page_from, notify=bookChanged)

    def _get_page_to(self) -> int:
        return self._page_to

    pageTo = Property(int, _get_page_to, notify=bookChanged)

    # Exámenes antiguos (RF-09)
    def _get_exams(self) -> list[dict[str, Any]]:
        return [{"name": e.name, "pages": e.pages, "scanned": len(e.scanned)} for e in self._exams]

    exams = Property(list, _get_exams, notify=examsChanged)

    def _get_exam_count(self) -> int:
        return len(self._exams)

    examCount = Property(int, _get_exam_count, notify=examsChanged)

    def _get_max_exams(self) -> int:
        return MAX_EXAMS

    maxExams = Property(int, _get_max_exams, constant=True)

    def _get_exams_loading(self) -> bool:
        return self._exams_loading

    examsLoading = Property(bool, _get_exams_loading, notify=examsChanged)

    def _get_exam_error(self) -> str:
        return self._exam_error

    examError = Property(str, _get_exam_error, notify=examsChanged)

    def _get_exam_error_file(self) -> str:
        return self._exam_error_file

    examErrorFile = Property(str, _get_exam_error_file, notify=examsChanged)

    # Estimación (RF-10)
    def _get_estimating(self) -> bool:
        return self._estimating

    estimating = Property(bool, _get_estimating, notify=estimateChanged)

    def _est(self) -> Any:
        return self._prep.estimate if self._prep else None

    def _get_est_eur(self) -> float:
        return self._est().eur if self._prep else 0.0

    estimateEur = Property(float, _get_est_eur, notify=estimateChanged)

    def _get_est_usd(self) -> float:
        return self._est().usd if self._prep else 0.0

    estimateUsd = Property(float, _get_est_usd, notify=estimateChanged)

    def _get_est_calls(self) -> int:
        return self._est().calls if self._prep else 0

    estimateCalls = Property(int, _get_est_calls, notify=estimateChanged)

    def _get_est_cached(self) -> int:
        return self._est().cached_calls if self._prep else 0

    estimateCachedCalls = Property(int, _get_est_cached, notify=estimateChanged)

    def _get_est_seconds(self) -> float:
        return self._est().seconds if self._prep else 0.0

    estimateSeconds = Property(float, _get_est_seconds, notify=estimateChanged)

    def _get_sel_pages(self) -> int:
        if not self._prep:
            return 0
        return sum(c.end_page - c.start_page + 1 for c in self._prep.selected)

    selectedPages = Property(int, _get_sel_pages, notify=estimateChanged)

    def _get_scanned(self) -> int:
        return len(self._prep.scanned_pages) if self._prep else 0

    scannedPages = Property(int, _get_scanned, notify=estimateChanged)

    def _get_selected(self) -> list[dict[str, Any]]:
        if not self._prep:
            return []
        return [
            {"title": c.title, "firstPage": c.start_page, "lastPage": c.end_page}
            for c in self._prep.selected
        ]

    selectedChapters = Property(list, _get_selected, notify=estimateChanged)

    # Progreso (RF-11)
    def _get_stage(self) -> str:
        return str(self._progress.stage) if self._progress else ""

    stage = Property(str, _get_stage, notify=progressChanged)

    def _get_fraction(self) -> float:
        return self._fraction

    fraction = Property(float, _get_fraction, notify=progressChanged)

    def _get_step_done(self) -> int:
        return self._progress.done if self._progress else 0

    stepDone = Property(int, _get_step_done, notify=progressChanged)

    def _get_step_total(self) -> int:
        return self._progress.total if self._progress else 0

    stepTotal = Property(int, _get_step_total, notify=progressChanged)

    def _get_chapter(self) -> int:
        return (self._progress.chapter or 0) if self._progress else 0

    chapterIndex = Property(int, _get_chapter, notify=progressChanged)

    def _get_chapter_total(self) -> int:
        return (self._progress.chapters or 0) if self._progress else 0

    chapterTotal = Property(int, _get_chapter_total, notify=progressChanged)

    def _get_chapter_title(self) -> str:
        return (self._progress.chapter_title or "") if self._progress else ""

    chapterTitle = Property(str, _get_chapter_title, notify=progressChanged)

    def _get_cost_eur(self) -> float:
        return to_eur(self._progress.cost_usd) if self._progress else 0.0

    costEur = Property(float, _get_cost_eur, notify=progressChanged)

    def _get_eta(self) -> float:
        eta = self._progress.eta_seconds if self._progress else None
        return -1.0 if eta is None else eta

    etaSeconds = Property(float, _get_eta, notify=progressChanged)

    def _get_running(self) -> bool:
        return self._cancel is not None

    running = Property(bool, _get_running, notify=progressChanged)

    def _get_regenerating(self) -> bool:
        return self._regenerating

    regenerating = Property(bool, _get_regenerating, notify=historyChanged)

    def _get_cancelling(self) -> bool:
        return self._cancelling

    cancelling = Property(bool, _get_cancelling, notify=progressChanged)

    # Listo (RF-16)
    def _get_summary(self) -> str:
        return str(self._done.summary) if self._done else ""

    summaryPath = Property(str, _get_summary, notify=resultChanged)

    def _get_outline(self) -> str:
        return str(self._done.outline) if self._done else ""

    outlinePath = Property(str, _get_outline, notify=resultChanged)

    def _get_result_cost(self) -> float:
        return to_eur(self._done.cost_usd) if self._done else 0.0

    resultCostEur = Property(float, _get_result_cost, notify=resultChanged)

    def _get_failed(self) -> str:
        if not self._done:
            return ""
        return ", ".join(f"{a}–{b}" if a != b else str(a) for a, b in self._done.failed_pages)

    failedPages = Property(str, _get_failed, notify=resultChanged)

    def _get_exams_failed(self) -> bool:
        return self._done.exams_failed if self._done else False

    examsFailed = Property(bool, _get_exams_failed, notify=resultChanged)

    # Errores y avisos (§8)
    def _get_error(self) -> str:
        return self._error

    error = Property(str, _get_error, notify=errorChanged)

    def _get_error_where(self) -> str:
        return self._error_where

    errorWhere = Property(str, _get_error_where, notify=errorChanged)

    def _get_error_actions(self) -> list[str]:
        return [str(a) for a in ErrorKind[self._error].actions] if self._error else []

    errorActions = Property(list, _get_error_actions, notify=errorChanged)

    def _get_notice(self) -> str:
        return self._notice

    notice = Property(str, _get_notice, notify=noticeChanged)

    # Ajustes (RF-17)
    def _get_model(self) -> str:
        return self._model()

    model = Property(str, _get_model, notify=settingsChanged)

    def _get_models(self) -> list[str]:
        return list(PRICES)

    models = Property(list, _get_models, constant=True)

    def _get_output_dir(self) -> str:
        return str(self._settings.output_path)

    outputDir = Property(str, _get_output_dir, notify=settingsChanged)

    def _get_language(self) -> str:
        return self._language() or ""

    language = Property(str, _get_language, notify=settingsChanged)

    def _get_languages(self) -> list[str]:
        return list(LANGUAGE_NAMES)

    languages = Property(list, _get_languages, constant=True)

    def _get_cache_entries(self) -> int:
        return self._cache.count()

    cacheEntries = Property(int, _get_cache_entries, notify=settingsChanged)

    # Historial y reanudación (RF-18, RNF-06)
    def _get_history(self) -> HistoryModel:
        return self.history

    historyModel = Property(QObject, _get_history, constant=True)

    def _get_history_count(self) -> int:
        return len(self.history)

    historyCount = Property(int, _get_history_count, notify=historyChanged)

    def _get_resume_title(self) -> str:
        return str(self._resume["title"]) if self._resume else ""

    resumeTitle = Property(str, _get_resume_title, notify=historyChanged)

    # --- Clave de API --------------------------------------------------------------

    @Slot(str)
    def testKey(self, key: str) -> None:
        """Prueba la clave (sin gastar) y, si vale, la guarda en el llavero."""
        key = key.strip()
        if not key:
            self._key_status, self._key_error = "error", ErrorKind.INVALID_KEY.name
            self.keyChanged.emit()
            return
        self._key_status, self._key_error = "checking", ""
        self.keyChanged.emit()
        model = self._settings.model

        def job(_report: Report) -> object:
            self._key_checker(key, model)
            return None

        self._spawn(job, lambda _r: self._key_ok(key), self._key_failed)

    def _key_ok(self, key: str) -> None:
        try:
            settings.set_api_key(key)
        except Exception as exc:
            log.warning("No se ha podido guardar la clave en el llavero: %s", type(exc).__name__)
            self._key_failed(CribaError(ErrorKind.NO_KEY))
            return
        log.info("Clave de API comprobada y guardada en el llavero")
        self._has_key = True
        self._key_status, self._key_error = "ok", ""
        self.keyChanged.emit()
        if self._error in {ErrorKind.INVALID_KEY.name, ErrorKind.NO_KEY.name}:
            self._set_error(None)
        self._set_screen("home")

    def _key_failed(self, exc: BaseException) -> None:
        kind = _error_kind(exc)
        log.info("La clave no se ha podido comprobar: %s", kind.name)
        self._key_status, self._key_error = "error", kind.name
        self.keyChanged.emit()

    @Slot()
    def changeKey(self) -> None:
        """Abre el asistente de la clave."""
        if self._busy():
            return
        self._key_status, self._key_error = "", ""
        self.keyChanged.emit()
        self._set_screen("setup")

    @Slot()
    def cancelKeyChange(self) -> None:
        """Vuelve del asistente sin cambiar la clave (solo si ya había una)."""
        if self._has_key:
            self._set_screen("home")

    @Slot()
    def forgetKey(self) -> None:
        """Borra la clave del llavero."""
        if self._busy():
            return
        settings.delete_api_key()
        self._has_key = settings.get_api_key() is not None
        self.keyChanged.emit()
        if not self._has_key:
            self._set_screen("setup")

    # --- Libro ----------------------------------------------------------------------

    @Slot(str)
    def openBook(self, url: str) -> None:
        """Lee el PDF y estima el coste (gratis, en local)."""
        self._open(_local_path(url), None)

    def _open(self, path: Path, saved: dict[str, Any] | None) -> None:
        # PyMuPDF no admite dos hilos a la vez: no se lee el libro mientras se leen exámenes.
        if self._loading or self._exams_loading or self._busy():
            return
        self._book_model = None
        self._book_language = None
        if saved:
            if saved.get("modelo") in PRICES:
                self._book_model = str(saved["modelo"])
            if "idioma" in saved:
                idioma = saved["idioma"]
                self._book_language = (idioma if idioma in LANGUAGE_NAMES else None,)
        self._loading, self._load_fraction = True, 0.0
        self._set_error(None)
        self._set_notice("")
        self.bookChanged.emit()
        model = self._model()
        cache = self._cache
        output_dir = self._settings.output_path
        language = self._language()

        def job(report: Report) -> object:
            title = (saved or {}).get("asignatura") or ingest.validate(path).title
            options = Options(asignatura=title, idioma=language, output_dir=output_dir)
            prep = prepare(path, options, cache, model, on_progress=report)
            # Al reanudar, los exámenes de entonces (si siguen ahí y se pueden leer).
            found, _ = _read_exams([Path(p) for p in (saved or {}).get("exams") or []])
            return title, prep, found

        self._spawn(
            job,
            lambda r: self._book_ready(r[0], r[1], saved, r[2]),
            self._book_failed,
            self._book_progress,
        )

    def _book_progress(self, p: Progress) -> None:
        self._load_fraction = p.fraction
        self.bookChanged.emit()

    def _book_ready(
        self,
        title: str,
        prep: Prepared,
        saved: dict[str, Any] | None,
        saved_exams: list[Exam],
    ) -> None:
        self._prep = prep
        if saved is not None:
            self._exams = saved_exams
            self._set_exam_error(None)
        book_sha = prep.book.info.sha256
        if any(e.sha256 == book_sha for e in self._exams):  # el libro no es un examen
            self._exams = [e for e in self._exams if e.sha256 != book_sha]
            self.examsChanged.emit()
        self._subject = title
        self._done = None
        saved = saved or {}
        self._level = saved.get("nivel") or "normal"
        self._exam = saved.get("tipo_examen") or "mixto"
        pr = saved.get("page_range") or (0, 0)
        self._page_from, self._page_to = int(pr[0]), int(pr[1])
        wanted = saved.get("chapters")
        self.chapters.reset(
            [
                ChapterRow(c.title, c.start_page, c.end_page, wanted is None or i in wanted)
                for i, c in enumerate(prep.chapters)
            ]
        )
        self._loading = False
        log.info(
            "Libro listo: %d páginas, %d capítulos", prep.book.info.page_count, len(prep.chapters)
        )
        self.bookChanged.emit()
        self.resultChanged.emit()
        if saved or self._exams:
            self._start_replan()
        else:
            self.estimateChanged.emit()
        self._set_screen("home")

    def _book_failed(self, exc: BaseException) -> None:
        self._loading = False
        self.bookChanged.emit()
        self._set_error(_error_kind(exc), "book")

    @Slot()
    def closeBook(self) -> None:
        """Quita el libro cargado (Elegir otro archivo)."""
        if self._busy():
            return
        self._prep = None
        self.chapters.reset([])
        self._set_error(None)
        self.bookChanged.emit()
        self.estimateChanged.emit()

    @Slot(int, bool)
    def setChapterChecked(self, row: int, checked: bool) -> None:
        """Marca o desmarca un capítulo."""
        self.chapters.set_checked(row, checked)

    @Slot(bool)
    def setAllChapters(self, checked: bool) -> None:
        """Marca o desmarca todos los capítulos."""
        self.chapters.set_all(checked)

    @Slot(int, int)
    def setPageRange(self, first: int, last: int) -> None:
        """Rango de páginas opcional; 0, 0 lo quita."""
        total = self._get_page_count()
        if first and last:
            first, last = max(1, min(first, total)), max(1, min(last, total))
            first, last = min(first, last), max(first, last)
        else:
            first = last = 0
        if (first, last) != (self._page_from, self._page_to):
            self._page_from, self._page_to = first, last
            self.bookChanged.emit()
            self._schedule_replan()

    # --- Exámenes antiguos (RF-09) ---------------------------------------------------

    def _set_exam_error(self, kind: ErrorKind | None, file: str = "") -> None:
        self._exam_error = kind.name if kind else ""
        self._exam_error_file = file if kind else ""
        self.examsChanged.emit()

    @Slot(list)
    def addExams(self, urls: list[str]) -> None:
        """Lee los exámenes elegidos (en local, gratis) y rehace la estimación."""
        if self._exams_loading or self._loading or self._busy():  # PyMuPDF: un hilo cada vez
            return
        known = {e.path for e in self._exams}
        wanted = [p for p in dict.fromkeys(_local_path(str(u)) for u in urls) if p not in known]
        if not wanted:
            return
        if len(self._exams) + len(wanted) > MAX_EXAMS:
            self._set_exam_error(ErrorKind.TOO_MANY_EXAMS)
            return
        self._exams_loading = True
        self._set_exam_error(None)

        def job(_report: Report) -> object:
            return _read_exams(wanted)

        self._spawn(job, lambda r: self._exams_read(r[0], r[1]), self._exams_failed)

    def _exams_read(self, found: list[Exam], problem: tuple[str, ErrorKind] | None) -> None:
        self._exams_loading = False
        shas = {e.sha256 for e in self._exams}
        if self._prep is not None:
            shas.add(self._prep.book.info.sha256)  # el propio libro no es un examen
        added: list[Exam] = []
        for exam in found:
            if exam.sha256 in shas:
                continue
            if limits_problem([*self._exams, *added, exam]):  # no caben en una llamada
                problem = problem or (exam.name, ErrorKind.EXAMS_TOO_BIG)
                continue
            shas.add(exam.sha256)
            added.append(exam)
        self._exams += added
        log.info("Exámenes añadidos: %d (en total %d)", len(added), len(self._exams))
        if problem:
            self._set_exam_error(problem[1], problem[0])
        else:
            self.examsChanged.emit()
        if added:
            self._schedule_replan()

    def _exams_failed(self, exc: BaseException) -> None:
        self._exams_loading = False
        self._set_exam_error(_error_kind(exc))

    @Slot(int)
    def removeExam(self, index: int) -> None:
        """Quita un examen de la lista."""
        if self._busy() or not 0 <= index < len(self._exams):
            return
        del self._exams[index]
        self._set_exam_error(None)
        self._schedule_replan()

    @Slot()
    def dismissExamError(self) -> None:
        """Oculta el aviso de un examen que no se ha podido añadir."""
        self._set_exam_error(None)

    def _schedule_replan(self) -> None:
        if self._prep is None or self._loading or self._cancel is not None:
            return
        self._estimating = True
        self.estimateChanged.emit()
        self._replan_timer.start()

    def _start_replan(self) -> None:
        if self._prep is None:
            return
        if self._replan_running:
            self._replan_dirty = True
            return
        self._replan_running, self._replan_dirty = True, False
        self._estimating = True
        self.estimateChanged.emit()
        prep, options, cache = self._prep, self._options(), self._cache
        exam_files = list(self._exams)  # ya leídos: el hilo no vuelve a abrir los PDF
        if prep.model != self._model():
            prep = replace(prep, model=self._model())

        def job(_report: Report) -> object:
            return replan(prep, options, cache, exam_files)

        self._spawn(job, self._replanned, self._replan_failed)

    def _replanned(self, prep: Prepared) -> None:
        self._replan_running = False
        if self._prep is not None and prep.book is self._prep.book:
            self._prep = prep
            if prep.model != self._model():  # el modelo cambió mientras se estimaba
                self._replan_dirty = True
        if self._replan_dirty and self._cancel is None:
            self._start_replan()
            return
        self._estimating = False
        self.estimateChanged.emit()

    def _replan_failed(self, exc: BaseException) -> None:
        self._replan_running = False
        if self._replan_dirty:
            self._start_replan()
            return
        self._estimating = False
        self.estimateChanged.emit()
        self._set_error(_error_kind(exc), "book")

    # --- Procesar ---------------------------------------------------------------------

    @Slot()
    def start(self) -> None:
        """Empieza a procesar con la IA (después de confirmar el coste)."""
        if self._prep is None or self._cancel is not None or self._exams_loading:
            return
        key = settings.get_api_key()
        if not key:
            self._set_error(ErrorKind.NO_KEY, "run")
            self.changeKey()
            return
        options = self._options()
        prep, cache = self._prep, self._cache
        exam_files = list(self._exams)
        if prep.model != self._model():
            prep = replace(prep, model=self._model())
        try:
            llm = self._llm_factory(key, prep.model)
        except Exception as exc:
            self._set_error(_error_kind(exc), "run")
            return
        self._cancel = token = CancelToken()
        self._cancelling = False
        self._progress = Progress(Stage.ANALYZING, 0, 0)
        self._fraction = 0.0
        self._done = None
        self._set_error(None)
        self._set_notice("")
        self.progressChanged.emit()
        self._set_screen("processing")
        log.info(
            "Procesando «%s» con %s; estimado %.2f $ en %d llamadas (%.0f s)",
            options.asignatura,
            prep.model,
            prep.estimate.usd,
            prep.estimate.calls,
            prep.estimate.seconds,
        )

        def job(report: Report) -> object:
            fresh = replan(prep, options, cache, exam_files)
            return run(fresh, options, llm, cache, on_progress=report, cancel=token)

        self._spawn(job, self._run_done, self._run_failed, self._run_progress)

    def _run_progress(self, p: Progress) -> None:
        self._progress = p
        self._fraction = max(self._fraction, overall_fraction(p))
        self._set_notice(p.notice or "")
        self.progressChanged.emit()

    def _run_done(self, result: RunResult) -> None:
        self._cancel = None
        log.info(
            "Listo: coste real %.2f $ en %d llamadas (%d desde la caché)",
            result.cost_usd,
            result.calls,
            result.cached_calls,
        )
        self._done = Done(
            result.summary_pdf,
            result.outline_pdf,
            result.cost_usd,
            result.failed_pages,
            result.exams_failed,
        )
        self._fraction = 1.0
        self.progressChanged.emit()
        self.resultChanged.emit()
        self.refreshHistory()
        self.settingsChanged.emit()  # entradas de la caché
        self._set_screen("done")

    def _run_failed(self, exc: BaseException) -> None:
        self._cancel = None
        self._cancelling = False
        self.progressChanged.emit()
        self.refreshHistory()
        if isinstance(exc, Cancelled):
            self._progress = None
            self._set_notice("cancelled")
            self._set_screen("home")
            self._schedule_replan()  # lo hecho ya no cuesta
            return
        kind = _error_kind(exc)
        log.warning("Procesado detenido: %s", kind.name)
        self._set_error(kind, "run")

    @Slot()
    def cancel(self) -> None:
        """Cancela (lo hecho queda en la caché, RF-12)."""
        if self._cancel is not None:
            self._cancel.cancel()
            self._cancelling = True
            self.progressChanged.emit()

    @Slot()
    def backToHome(self) -> None:
        """Vuelve a Inicio desde un error del procesado."""
        if self._cancel is None:
            self._progress = None
            self._set_error(None)
            self._set_screen("home")
            self._schedule_replan()

    @Slot()
    def processAnother(self) -> None:
        """Procesar otro libro."""
        if self._busy():
            return
        self._done = None
        self._progress = None
        self.resultChanged.emit()
        self._exams = []
        self._set_exam_error(None)
        self.closeBook()
        self._set_screen("home")

    @Slot()
    def dismissError(self) -> None:
        """Oculta el mensaje de error."""
        self._set_error(None)

    @Slot()
    def dismissNotice(self) -> None:
        """Oculta el aviso."""
        self._set_notice("")

    # --- Archivos ---------------------------------------------------------------------

    @Slot(str, result=bool)
    def openFile(self, path: str) -> bool:
        """Abre un archivo con la app del sistema."""
        return bool(path) and QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    @Slot(str, result=bool)
    def showInFolder(self, path: str) -> bool:
        """Abre la carpeta que contiene ``path``."""
        target = Path(path)
        folder = target if target.is_dir() else target.parent
        return bool(path) and QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    @Slot(result=bool)
    def openConsole(self) -> bool:
        """Abre la consola de Anthropic (saldo y claves)."""
        return QDesktopServices.openUrl(QUrl(CONSOLE_URL))

    @Slot(result=bool)
    def openLogs(self) -> bool:
        """Ajustes > Abrir carpeta de logs (RNF-07)."""
        return QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.log_dir())))

    # --- Ajustes ------------------------------------------------------------------------

    @Slot(str)
    def setModel(self, model: str) -> None:
        """Cambia el modelo (y rehace la estimación)."""
        if self._busy():
            return
        if model in PRICES and model != self._model():
            self._settings.model = model
            self._book_model = None
            settings.save(self._settings)
            self._schedule_replan()
            self.settingsChanged.emit()

    @Slot(str)
    def setOutputDir(self, url: str) -> None:
        """Carpeta donde se guardan los PDF."""
        if self._busy():
            return
        path = _local_path(url) if url else None
        self._settings.output_dir = str(path) if path else None
        settings.save(self._settings)
        if self._error in {ErrorKind.DISK_FULL.name, ErrorKind.CANNOT_WRITE.name}:
            self._set_error(None)
        self.settingsChanged.emit()

    @Slot(str)
    def setLanguage(self, code: str) -> None:
        """Idioma de los PDF; vacío = el del libro."""
        if self._busy():
            return
        value = code if code in LANGUAGE_NAMES else None
        if value != self._language():
            self._settings.language = value
            self._book_language = None
            settings.save(self._settings)
            self.settingsChanged.emit()
            self._schedule_replan()

    @Slot()
    def clearCache(self) -> None:
        """Borra la caché (lo procesado se volvería a pagar)."""
        if self._busy():
            return
        self._cache.clear()
        log.info("Caché borrada")
        self.settingsChanged.emit()
        self.refreshHistory()
        self._schedule_replan()

    # --- Historial y reanudación -----------------------------------------------------

    @Slot()
    def refreshHistory(self) -> None:
        """Relee el historial y si hay algo a medias."""
        rows = []
        for job in self._cache.jobs("done"):
            outs = [*job.outputs, "", "", ""][:3]
            rows.append(
                HistoryRow(
                    job.id,
                    job.title,
                    job.updated,
                    job.cost_usd,
                    outs[0],
                    outs[1],
                    outs[2],
                    all(Path(o).exists() for o in outs[:2] if o),
                )
            )
        self.history.reset(rows)
        self._resume = None
        finished: dict[str, int] = {}
        for done in self._cache.jobs("done"):
            finished[done.book_sha] = max(finished.get(done.book_sha, 0), done.id)
        for job in self._cache.interrupted_jobs():
            if finished.get(job.book_sha, 0) > job.id:
                continue  # ese libro se terminó después (quizá con otras opciones)
            if job.pdf_path.exists():
                self._resume = {"title": job.title, "pdf": job.pdf_path, "options": job.options}
                break
        self.historyChanged.emit()

    @Slot()
    def resume(self) -> None:
        """Continuar donde lo dejaste: carga el libro con las opciones de entonces."""
        if self._resume and not self._busy():
            self._open(Path(self._resume["pdf"]), dict(self._resume["options"]))

    @Slot(int)
    def regenerate(self, job_id: int) -> None:
        """Vuelve a generar los PDF desde «datos.json» (sin IA, sin coste)."""
        if self._regenerating or self._busy():
            return
        row = self.history.row(job_id)
        if row is None or not row.data:
            self._set_error(ErrorKind.NOT_FOUND, "history")
            return
        data = Path(row.data)
        out_dir = data.parent

        def job(_report: Report) -> object:
            try:
                libro = Libro.model_validate_json(data.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise CribaError(ErrorKind.NOT_FOUND, detail=repr(exc)) from exc
            summary, outline = render_book(libro, out_dir)
            return Done(summary, outline, 0.0, list(libro.paginas_no_procesadas))

        self._regenerating = True
        self.historyChanged.emit()
        self._spawn(job, self._regenerated, self._regenerate_failed)

    def _regenerate_failed(self, exc: BaseException) -> None:
        self._regenerating = False
        self.historyChanged.emit()
        self._set_error(_error_kind(exc), "history")

    def _regenerated(self, done: Done) -> None:
        self._regenerating = False
        self._done = done
        self.resultChanged.emit()
        self.refreshHistory()
        self._set_screen("done")
