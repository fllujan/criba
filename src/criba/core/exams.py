"""Análisis de exámenes de años anteriores (RF-09, spec §6 etapa 6).

Los exámenes se leen en local (gratis). Antes del reduce, una sola llamada con el
prompt ``exams`` sitúa cada pregunta en un capítulo del libro. Las páginas
escaneadas o fotografiadas van como imagen en esa misma llamada, sin OCR aparte.
Después, cada capítulo con preguntas recibe la nota ``exam_topics`` en su síntesis,
sube un nivel de prioridad y lleva la etiqueta «Ha caído en examen».
"""

from dataclasses import dataclass
from pathlib import Path

from criba.core import ingest, ocr, schemas
from criba.core.analyze import StudyOptions, prompt, system_for
from criba.core.cache import make_key
from criba.core.errors import CribaError, ErrorKind
from criba.core.llm import Content, LLMRequest
from criba.core.structure import Chapter

MAX_EXAMS = 10
MAX_EXAM_PAGES = 50
# Todo va en una sola llamada: estos topes la mantienen dentro de los límites de la API
# (imágenes por petición, tamaño y salida máxima).
MAX_TOTAL_PAGES = 60
MAX_SCANNED_PAGES = 20
MAX_SECTIONS = 12  # apartados por capítulo en la lista que recibe la IA
EXAMS_BASE_TOKENS = 8_000  # salida + razonamiento
EXAMS_TOKENS_PER_PAGE = 1_500
EXAMS_MAX_TOKENS = 64_000


@dataclass(frozen=True, slots=True)
class Exam:
    """Examen antiguo leído en local."""

    path: Path
    name: str
    sha256: str
    pages: int
    text: str  # páginas con texto, con marcas [p. N]
    scanned: tuple[int, ...]  # páginas que van como imagen


def read_exam(path: Path) -> Exam:
    """Lee y valida un examen. Lanza ``CribaError`` si no sirve."""
    info = ingest.validate(path)
    if info.page_count > MAX_EXAM_PAGES:  # antes de leerlo entero
        raise CribaError(ErrorKind.EXAM_TOO_LONG, detail=f"{info.page_count} páginas")
    book = ingest.open_book(path)
    text = "\n\n".join(
        f"[p. {p.number}]\n{p.text}" for p in book.pages if not p.is_scanned and p.text.strip()
    )
    scanned = tuple(book.scanned_pages)
    if not text and not scanned:
        raise CribaError(ErrorKind.NO_TEXT, detail=str(path))
    return Exam(path, path.name, book.info.sha256, book.info.page_count, text, scanned)


def limits_problem(exams: list[Exam]) -> ErrorKind | None:
    """Si el conjunto de exámenes no cabe en una llamada, el motivo."""
    if len(exams) > MAX_EXAMS:
        return ErrorKind.TOO_MANY_EXAMS
    pages = sum(e.pages for e in exams)
    scanned = sum(len(e.scanned) for e in exams)
    if pages > MAX_TOTAL_PAGES or scanned > MAX_SCANNED_PAGES:
        return ErrorKind.EXAMS_TOO_BIG
    return None


def max_tokens(exams: list[Exam]) -> int:
    """Salida máxima de la llamada: crece con las páginas de los exámenes."""
    pages = sum(e.pages for e in exams)
    return min(EXAMS_MAX_TOKENS, EXAMS_BASE_TOKENS + pages * EXAMS_TOKENS_PER_PAGE)


def chapter_list(chapters: list[Chapter]) -> str:
    """«1. Título (pp. 2–9). Apartados: A; B» por capítulo."""
    lines = []
    for i, ch in enumerate(chapters, 1):
        line = f"{i}. {ch.title} (pp. {ch.start_page}–{ch.end_page})."
        titles = list(dict.fromkeys(s.title for s in ch.sections))[:MAX_SECTIONS]
        if titles:
            line += " Apartados: " + "; ".join(titles) + "."
        lines.append(line)
    return "\n".join(lines)


def exams_request(opts: StudyOptions, chapters: list[Chapter], exams: list[Exam]) -> LLMRequest:
    """Petición que sitúa cada pregunta de los exámenes en un capítulo."""
    content: Content = [f"Capítulos del libro ({len(chapters)}):", chapter_list(chapters)]
    for exam in exams:
        if exam.text:
            content += [f"Examen «{exam.name}»:", exam.text]
        for number, image in zip(
            exam.scanned, ocr.render_pages(exam.path, list(exam.scanned)), strict=True
        ):
            content += [f"Examen «{exam.name}», página {number} (escaneada):", image]
    return LLMRequest(
        system=system_for("exams", opts),
        content=content,
        schema=schemas.AnalisisExamenes,
        max_tokens=max_tokens(exams),
        context={"capitulos": len(chapters)},
    )


def fingerprint(chapters: list[Chapter], exams: list[Exam]) -> str:
    """Identifica el análisis: cambia con los exámenes o con la lista de capítulos."""
    parts = sorted(e.sha256 for e in exams)  # el orden en que se añadieron no importa
    parts += [f"{c.title}|{c.start_page}|{c.end_page}" for c in chapters]
    return make_key(*parts)[:16]


Topics = dict[int, list[schemas.PreguntaExamen]]


def topics_by_chapter(result: schemas.AnalisisExamenes) -> Topics:
    """Preguntas por capítulo (índice desde 0), sin temas repetidos."""
    out: Topics = {}
    for q in result.preguntas:
        if q.capitulo is None:
            continue
        found = out.setdefault(q.capitulo - 1, [])
        if all(t.tema.casefold() != q.tema.casefold() for t in found):
            found.append(q)
    return out


def topic_names(questions: list[schemas.PreguntaExamen]) -> list[str]:
    """Los temas que han caído, para la etiqueta del PDF."""
    return [q.tema for q in questions]


def topics_note(questions: list[schemas.PreguntaExamen]) -> str:
    """Nota para la síntesis del capítulo con lo que ha caído."""
    lines = "\n".join(f"- {q.tema}: «{q.pregunta}»" for q in questions)
    return prompt("exam_topics").render(preguntas=lines)
