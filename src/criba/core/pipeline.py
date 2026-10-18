"""Orquestación de las siete etapas (spec §6) y eventos de progreso (RF-11).

Uso en dos pasos, como en la interfaz:

1. ``prepare()``: lee el libro y estima el coste. Es local y gratis (RF-10).
2. ``run()``: hace las llamadas a la IA, guarda cada resultado en la caché y
   genera el JSON final. Se puede cancelar en cualquier momento (RF-12); lo ya
   pagado queda en la caché y, al repetir, solo se procesa lo que falta.
"""

import errno
import json
import logging
import re
import threading
import time
from collections.abc import Callable, Mapping
from concurrent.futures import FIRST_EXCEPTION, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from functools import partial
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from criba.core import analyze, ingest, ocr, schemas, structure
from criba.core.analyze import StudyOptions
from criba.core.cache import Cache, make_key
from criba.core.cost import ChapterPlan, ChunkPlan, Estimate, Usage, estimate, estimate_tokens
from criba.core.errors import CribaError, ErrorKind
from criba.core.llm import LLMCallError, LLMClient, LLMRequest, Result, structured_call

log = logging.getLogger(__name__)

PARALLEL_CALLS = 4
OCR_TOKENS_PER_PAGE = 700  # texto estimado de una página escaneada, antes del OCR
MIN_CHAPTER_TOKENS = 120  # por debajo (portadas, páginas en blanco) no se gasta en la IA
M = TypeVar("M", bound=BaseModel)


class Stage(StrEnum):
    """Etapas que ve el usuario."""

    READING = "leyendo"
    OCR = "ocr"
    ANALYZING = "analizando"
    SYNTHESIZING = "sintetizando"
    RENDERING = "generando"
    DONE = "listo"


@dataclass(frozen=True, slots=True)
class Progress:
    """Evento de progreso."""

    stage: Stage
    done: int
    total: int
    chapter: int | None = None  # 1..N
    chapters: int | None = None
    chapter_title: str | None = None
    cost_usd: float = 0.0
    eta_seconds: float | None = None

    @property
    def fraction(self) -> float:
        """Avance de la etapa entre 0 y 1."""
        return self.done / self.total if self.total else 1.0


OnProgress = Callable[[Progress], None]


class Cancelled(Exception):  # noqa: N818 (es un evento, no un error)
    """El usuario ha cancelado. Lo procesado está en la caché."""


class CancelToken:
    """Permite cancelar desde otro hilo (botón Cancelar)."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        """Pide la cancelación."""
        self._event.set()

    @property
    def cancelled(self) -> bool:
        """``True`` si se ha pedido cancelar."""
        return self._event.is_set()

    def check(self) -> None:
        """Lanza ``Cancelled`` si se ha pedido cancelar."""
        if self._event.is_set():
            raise Cancelled


@dataclass(frozen=True, slots=True)
class Options:
    """Lo que elige el usuario en la pantalla de inicio."""

    asignatura: str
    nivel: schemas.Nivel = "normal"
    tipo_examen: schemas.TipoExamen = "mixto"
    idioma: str | None = None  # None = el idioma del libro
    chapters: tuple[int, ...] | None = None  # índices de los capítulos detectados
    page_range: tuple[int, int] | None = None
    output_dir: Path = Path()

    def as_dict(self) -> dict[str, object]:
        """Opciones serializables (para el registro de trabajos)."""
        return {
            "asignatura": self.asignatura,
            "nivel": self.nivel,
            "tipo_examen": self.tipo_examen,
            "idioma": self.idioma,
            "chapters": list(self.chapters) if self.chapters is not None else None,
            "page_range": list(self.page_range) if self.page_range else None,
            "output_dir": str(self.output_dir),
        }


@dataclass(slots=True)
class Prepared:
    """Libro leído, capítulos elegidos y estimación (lo que muestra la confirmación)."""

    book: ingest.Book
    chapters: list[structure.Chapter]  # todos los detectados
    selected: list[structure.Chapter]  # recortados a la selección
    language: str
    study: StudyOptions
    model: str
    ocr_pending: list[list[int]]  # lotes de OCR que faltan
    estimate: Estimate

    @property
    def scanned_pages(self) -> list[int]:
        """Páginas escaneadas dentro de la selección."""
        return [p for batch in self.ocr_pending for p in batch]


@dataclass(slots=True)
class RunResult:
    """Resultado de ``run()``."""

    libro: schemas.Libro
    json_path: Path
    usage: Usage
    cost_usd: float
    calls: int
    cached_calls: int
    failed_pages: list[tuple[int, int]] = field(default_factory=list)


# --- Utilidades ----------------------------------------------------------------------


def safe_filename(name: str) -> str:
    """Nombre de archivo válido en macOS y Windows."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", name).strip().rstrip(".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:120] or "Criba"


def _select(chapters: list[structure.Chapter], options: Options) -> list[structure.Chapter]:
    chosen = (
        chapters
        if options.chapters is None
        else [c for i, c in enumerate(chapters) if i in set(options.chapters)]
    )
    if options.page_range is None:
        return list(chosen)
    lo, hi = options.page_range
    out = []
    for ch in chosen:
        start, end = max(ch.start_page, lo), min(ch.end_page, hi)
        if start <= end:
            out.append(replace(ch, start_page=start, end_page=end, sections=list(ch.sections)))
    return out


def _key(prep: Prepared, fragment: str, prompt_name: str) -> str:
    s = prep.study
    return make_key(
        prep.book.info.sha256,
        fragment,
        analyze.prompt(prompt_name).id,
        prep.model,
        s.nivel,
        s.tipo_examen,
        s.idioma,
        f"chunker{structure.CHUNKER_VERSION}",
    )


def _ocr_key(prep: Prepared, pages: list[int]) -> str:
    return make_key(prep.book.info.sha256, f"ocr-{pages}", analyze.prompt("ocr").id, prep.model)


def _chapter_fragment(chapter: structure.Chapter, analyses: list[schemas.ChunkAnalysis]) -> str:
    digest = make_key(*(a.model_dump_json() for a in analyses))[:16]
    return f"cap-{chapter.start_page}-{chapter.end_page}-{digest}"


def chapter_chunks(book: ingest.Book, chapter: structure.Chapter) -> list[structure.Chunk]:
    """Fragmentos del capítulo; ninguno si casi no tiene texto (no merece una llamada)."""
    chunks = structure.chunk_chapter(book, chapter)
    if sum(c.tokens for c in chunks) < MIN_CHAPTER_TOKENS:
        return []
    return chunks


def _apply_ocr(book: ingest.Book, result: schemas.OcrResultado) -> None:
    for page in result.paginas:
        if 1 <= page.pagina <= len(book.pages):
            book.pages[page.pagina - 1].set_ocr_text(page.texto)


# --- Paso 1: preparar (gratis) ---------------------------------------------------------


def prepare(
    pdf: Path,
    options: Options,
    cache: Cache,
    model: str,
    on_progress: OnProgress | None = None,
) -> Prepared:
    """Lee el libro, detecta capítulos y estima el coste sin llamar a la IA."""

    def on_page(done: int, total: int) -> None:
        if on_progress:
            on_progress(Progress(Stage.READING, done, total))

    book = ingest.open_book(pdf, on_page=on_page)
    chapters = structure.detect_chapters(book)
    language = options.idioma or ingest.detect_language(book)
    study = StudyOptions(options.asignatura, options.nivel, options.tipo_examen, language)
    prep = Prepared(book, chapters, [], language, study, model, [], Estimate(model=model))
    prep.selected = _select(chapters, options)

    # OCR: lo que ya está en caché se aplica ahora (gratis) y no se vuelve a pedir.
    selected_pages = {p for c in prep.selected for p in range(c.start_page, c.end_page + 1)}
    scanned = [p for p in book.scanned_pages if p in selected_pages]
    for batch in ocr.batches(scanned):
        hit = cache.get(_ocr_key(prep, batch))
        if hit:
            _apply_ocr(book, schemas.OcrResultado.model_validate_json(hit[0]))
        else:
            prep.ocr_pending.append(batch)
    prep.estimate = _estimate(prep, cache)
    return prep


def _cached[T: BaseModel](
    cache: Cache, key: str, schema: type[T], context: Mapping[str, object]
) -> T | None:
    hit = cache.get(key)
    return schema.model_validate_json(hit[0], context=context) if hit else None


def _book_key(prep: Prepared, capitulos: list[schemas.Capitulo]) -> str:
    digest = make_key(*(c.model_dump_json() for c in capitulos))[:16]
    return _key(prep, f"libro-{digest}", "synthesize_book")


def _estimate(prep: Prepared, cache: Cache) -> Estimate:
    """Estimación con lo que ya está en caché descontado (síntesis incluidas)."""
    pending = {p for batch in prep.ocr_pending for p in batch}
    plans: list[ChapterPlan] = []
    capitulos: list[schemas.Capitulo] | None = []
    for ch in prep.selected:
        chunks = chapter_chunks(prep.book, ch)
        context = {"paginas": (ch.start_page, ch.end_page)}
        analyses = [
            _cached(cache, _key(prep, c.id, "analyze_chunk"), schemas.ChunkAnalysis, context)
            for c in chunks
        ]
        chunk_plans = [
            ChunkPlan(c.tokens, c.end_page - c.start_page + 1, a is not None)
            for c, a in zip(chunks, analyses, strict=True)
        ]
        missing = sum(1 for p in range(ch.start_page, ch.end_page + 1) if p in pending)
        if missing:
            chunk_plans.append(ChunkPlan(missing * OCR_TOKENS_PER_PAGE, missing))
        synthesis = None
        done = [a for a in analyses if a is not None]
        if chunks and not missing and len(done) == len(chunks):
            key = _key(prep, _chapter_fragment(ch, done), "synthesize_chapter")
            synthesis = _cached(cache, key, schemas.SintesisCapitulo, context)
        plans.append(ChapterPlan(chunk_plans, cached=synthesis is not None))
        if capitulos is not None and chunk_plans:
            capitulos = (
                None if synthesis is None else [*capitulos, analyze.to_capitulo(ch, synthesis)]
            )
    book_cached = (
        bool(capitulos) and capitulos is not None and cache.has(_book_key(prep, capitulos))
    )
    system = max(
        estimate_tokens(analyze.system_for(name, prep.study))
        for name in ("analyze_chunk", "synthesize_chapter", "synthesize_book")
    )
    return estimate(
        model=prep.model,
        level=prep.study.nivel,
        system_tokens=system,
        chapters=plans,
        book_cached=book_cached,
        ocr_batches=[(len(b), False) for b in prep.ocr_pending],
    )


# --- Paso 2: procesar ---------------------------------------------------------------------


class _Runner:
    """Estado de una ejecución: coste, progreso y tiempos."""

    def __init__(
        self,
        prep: Prepared,
        llm: LLMClient,
        cache: Cache,
        on_progress: OnProgress | None,
        cancel: CancelToken,
    ) -> None:
        self.prep = prep
        self.llm = llm
        self.cache = cache
        self.on_progress = on_progress
        self.cancel = cancel
        self.usage = Usage()
        self.calls = 0
        self.cached_calls = 0
        self._durations: list[float] = []
        self._lock = threading.Lock()

    @property
    def cost_usd(self) -> float:
        return self.usage.cost_usd(self.prep.model)

    def eta(self, remaining_calls: int) -> float | None:
        with self._lock:
            if not self._durations:
                return None
            avg = sum(self._durations) / len(self._durations)
        return avg * remaining_calls / PARALLEL_CALLS

    def emit(self, progress: Progress) -> None:
        if self.on_progress:
            with self._lock:
                self.on_progress(progress)

    def call(self, key: str, kind: str, request: LLMRequest, schema: type[M]) -> M:
        """Llamada con caché: si ya se pagó, se reutiliza."""
        hit = self.cache.get(key)
        if hit is not None:
            with self._lock:
                self.calls += 1
                self.cached_calls += 1
            return schema.model_validate_json(hit[0], context=request.context)
        self.cancel.check()
        started = time.monotonic()
        result: Result[M] = structured_call(self.llm, request, schema)
        elapsed = time.monotonic() - started
        self.cache.put(
            key,
            book_sha=self.prep.book.info.sha256,
            kind=kind,
            payload=result.value.model_dump_json(),
            model=self.prep.model,
            usage=result.usage,
        )
        with self._lock:
            self.calls += 1
            self.usage += result.usage
            self._durations.append(elapsed)
        return result.value

    def parallel(self, tasks: list[Callable[[], None]]) -> None:
        """Ejecuta las tareas con 4 llamadas a la vez. Un error grave detiene el resto."""
        with ThreadPoolExecutor(max_workers=PARALLEL_CALLS) as pool:
            futures: list[Future[None]] = [pool.submit(t) for t in tasks]
            done, pending = wait(futures, return_when=FIRST_EXCEPTION)
            for fut in done:
                if (exc := fut.exception()) is not None:
                    self.cancel.cancel()  # que las demás tareas no empiecen llamadas nuevas
                    for p in pending:
                        p.cancel()
                    raise exc


def run(
    prep: Prepared,
    options: Options,
    llm: LLMClient,
    cache: Cache,
    *,
    on_progress: OnProgress | None = None,
    cancel: CancelToken | None = None,
) -> RunResult:
    """Procesa el libro con la IA y escribe ``{Asignatura} - datos.json``."""
    cancel = cancel or CancelToken()
    if llm.model != prep.model:
        raise ValueError("el cliente usa un modelo distinto del de la estimación")
    job = cache.start_job(
        book_sha=prep.book.info.sha256,
        pdf_path=prep.book.info.path,
        title=prep.study.asignatura,
        options=options.as_dict() | {"modelo": prep.model},
    )
    runner = _Runner(prep, llm, cache, on_progress, cancel)
    try:
        result = _run(runner, options)
    except Cancelled:
        cache.finish_job(job, "cancelled", cost_usd=runner.cost_usd)
        log.info("Cancelado. Coste hasta ahora: %.4f $", runner.cost_usd)
        raise
    except BaseException:
        cache.finish_job(job, "failed", cost_usd=runner.cost_usd)
        raise
    cache.finish_job(job, "done", outputs=[str(result.json_path)], cost_usd=result.cost_usd)
    return result


def _run(r: _Runner, options: Options) -> RunResult:  # noqa: PLR0915 (orquestación lineal)
    prep = r.prep
    book = prep.book

    # Etapa 3: OCR de páginas escaneadas.
    for i, batch in enumerate(prep.ocr_pending):
        r.emit(Progress(Stage.OCR, i, len(prep.ocr_pending), cost_usd=r.cost_usd))
        try:
            res = r.call(
                _ocr_key(prep, batch),
                "ocr",
                ocr.ocr_request(book.info.path, batch),
                schemas.OcrResultado,
            )
        except LLMCallError as exc:
            log.warning("OCR fallido en páginas %s: %s", batch, exc)
            continue
        _apply_ocr(book, res)
    if prep.ocr_pending:
        r.emit(
            Progress(Stage.OCR, len(prep.ocr_pending), len(prep.ocr_pending), cost_usd=r.cost_usd)
        )

    # Etapa 4: fragmentos (después del OCR, que añade texto).
    chunks = {i: chapter_chunks(book, ch) for i, ch in enumerate(prep.selected)}
    all_chunks = [(i, c) for i, cs in chunks.items() for c in cs]
    total_calls = len(all_chunks) + len(prep.selected) + 1
    analyses: dict[str, schemas.ChunkAnalysis] = {}
    failed: list[tuple[int, structure.Chunk]] = []
    done = 0

    counter = threading.Lock()

    def map_one(ch_index: int, chunk: structure.Chunk) -> None:
        nonlocal done
        request = analyze.chunk_request(prep.study, chunk)
        try:
            analyses[chunk.id] = r.call(
                _key(prep, chunk.id, "analyze_chunk"), "chunk", request, schemas.ChunkAnalysis
            )
        except LLMCallError as exc:
            log.warning("Fragmento %s fallido: %s", chunk.id, exc)
            failed.append((ch_index, chunk))
        with counter:
            done += 1
            current = done
        r.emit(
            Progress(
                Stage.ANALYZING,
                current,
                len(all_chunks),
                chapter=ch_index + 1,
                chapters=len(prep.selected),
                chapter_title=prep.selected[ch_index].title,
                cost_usd=r.cost_usd,
                eta_seconds=r.eta(total_calls - current),
            )
        )

    # Etapa 5: map.
    r.emit(Progress(Stage.ANALYZING, 0, len(all_chunks), chapters=len(prep.selected)))
    r.parallel([partial(map_one, i, c) for i, c in all_chunks])
    # RNF-05: los fallidos se reintentan una vez al final.
    retry, failed[:] = list(failed), []
    for i, c in retry:
        r.cancel.check()
        done -= 1
        map_one(i, c)

    # Etapa 6: reduce por capítulo.
    capitulos: dict[int, schemas.Capitulo] = {}
    unprocessed: list[tuple[int, int]] = [(c.start_page, c.end_page) for _, c in failed]
    synth_done = 0

    def reduce_one(ch_index: int) -> None:
        nonlocal synth_done
        chapter = prep.selected[ch_index]
        parts = [analyses[c.id] for c in chunks[ch_index] if c.id in analyses]
        if parts:
            request = analyze.chapter_request(prep.study, chapter, parts)
            key = _key(prep, _chapter_fragment(chapter, parts), "synthesize_chapter")
            try:
                s = r.call(key, "chapter", request, schemas.SintesisCapitulo)
                capitulos[ch_index] = analyze.to_capitulo(chapter, s)
            except LLMCallError as exc:
                log.warning(
                    "Síntesis del capítulo %r fallida, se monta sin IA: %s", chapter.title, exc
                )
                capitulos[ch_index] = analyze.local_capitulo(chapter, parts)
        with counter:
            synth_done += 1
            current = synth_done
        r.emit(
            Progress(
                Stage.SYNTHESIZING,
                current,
                len(prep.selected) + 1,
                chapter=ch_index + 1,
                chapters=len(prep.selected),
                chapter_title=chapter.title,
                cost_usd=r.cost_usd,
                eta_seconds=r.eta(len(prep.selected) + 1 - current),
            )
        )

    r.parallel([partial(reduce_one, i) for i in range(len(prep.selected))])
    ordered = [capitulos[i] for i in sorted(capitulos)]

    # Etapa 6b: mapa del libro.
    mapa, conexiones = "", []
    if ordered:
        try:
            libro_ia = r.call(
                _book_key(prep, ordered),
                "book",
                analyze.book_request(prep.study, ordered),
                schemas.SintesisLibro,
            )
            mapa, conexiones = libro_ia.mapa, libro_ia.conexiones
        except LLMCallError as exc:
            log.warning("Mapa del libro fallido, se usa el de los capítulos: %s", exc)
            mapa = "\n\n".join(f"{c.titulo}: {c.resumen}" for c in ordered)
    r.emit(
        Progress(
            Stage.SYNTHESIZING, len(prep.selected) + 1, len(prep.selected) + 1, cost_usd=r.cost_usd
        )
    )

    if not ordered:
        raise CribaError(ErrorKind.NO_TEXT, detail="ningún fragmento se pudo procesar")

    # Etapa 7: resultado (los PDF se generan a partir de este JSON).
    r.emit(Progress(Stage.RENDERING, 0, 1, cost_usd=r.cost_usd))
    libro = schemas.Libro(
        asignatura=prep.study.asignatura,
        titulo_libro=book.info.title,
        archivo=book.info.path.name,
        sha256=book.info.sha256,
        paginas_libro=book.info.page_count,
        nivel=prep.study.nivel,
        tipo_examen=prep.study.tipo_examen,
        idioma=prep.language,
        modelo=prep.model,
        fecha=datetime.now(UTC).isoformat(timespec="seconds"),
        mapa=mapa,
        conexiones=conexiones,
        capitulos=ordered,
        paginas_no_procesadas=sorted(set(unprocessed)),
        paginas_ocr=book.ocr_pages,
        coste_usd=round(r.cost_usd, 6),
    )
    json_path = options.output_dir / f"{safe_filename(prep.study.asignatura)} - datos.json"
    try:
        options.output_dir.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(libro.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        kind = ErrorKind.DISK_FULL if exc.errno == errno.ENOSPC else ErrorKind.CANNOT_WRITE
        raise CribaError(kind, detail=repr(exc)) from exc
    r.emit(Progress(Stage.DONE, 1, 1, cost_usd=r.cost_usd))
    return RunResult(
        libro=libro,
        json_path=json_path,
        usage=r.usage,
        cost_usd=r.cost_usd,
        calls=r.calls,
        cached_calls=r.cached_calls,
        failed_pages=libro.paginas_no_procesadas,
    )
