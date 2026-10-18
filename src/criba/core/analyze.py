"""Etapas map (por fragmento) y reduce (por capítulo y por libro) del spec §6.

Aquí solo se construyen las peticiones y se combinan los resultados; las llamadas,
la caché y el paralelismo los gestiona ``pipeline``.
"""

from dataclasses import dataclass
from functools import cache

from criba.core import schemas
from criba.core.cost import LEVEL_PERCENT, target_words
from criba.core.llm import LLMRequest, Prompt, dumps, load_prompt
from criba.core.structure import Chapter, Chunk

EXAM_INSTRUCTIONS: dict[str, str] = {
    "test": "examen tipo test. Al menos el 70 % de las preguntas deben ser de tipo `test`; "
    "el resto, `corta`.",
    "desarrollo": "examen de desarrollo. Prioriza preguntas de tipo `desarrollo` y `corta`, "
    "y `problema` si el texto tiene ejercicios. Usa `test` solo si encaja muy bien.",
    "mixto": "examen mixto. Combina preguntas `test`, `corta` y `desarrollo`, y `problema` "
    "si el texto tiene ejercicios o cálculos.",
}
LANGUAGE_NAMES: dict[str, str] = {
    "es": "español",
    "en": "inglés",
    "fr": "francés",
    "pt": "portugués",
    "it": "italiano",
    "de": "alemán",
    "ca": "catalán",
}
CHUNK_MAX_TOKENS = 32_000
CHAPTER_MAX_TOKENS = 64_000
BOOK_MAX_TOKENS = 16_000


@dataclass(frozen=True, slots=True)
class StudyOptions:
    """Opciones que cambian el contenido de las respuestas."""

    asignatura: str
    nivel: schemas.Nivel = "normal"
    tipo_examen: schemas.TipoExamen = "mixto"
    idioma: str = "es"  # código del idioma de salida


@cache
def prompt(name: str) -> Prompt:
    """Prompt cargado una sola vez."""
    return load_prompt(name)


def system_for(name: str, opts: StudyOptions) -> str:
    """Instrucciones de sistema: iguales para todo el libro (se aprovecha la caché)."""
    return prompt(name).render(
        asignatura=opts.asignatura,
        nivel=opts.nivel,
        porcentaje=str(LEVEL_PERCENT[opts.nivel]),
        instrucciones_examen=EXAM_INSTRUCTIONS[opts.tipo_examen],
        idioma=LANGUAGE_NAMES.get(opts.idioma, opts.idioma),
    )


def chunk_request(opts: StudyOptions, chunk: Chunk) -> LLMRequest:
    """Petición de la etapa map para un fragmento."""
    pages = chunk.end_page - chunk.start_page + 1
    header = (
        f"Páginas de este fragmento: {chunk.start_page}–{chunk.end_page}.\n"
        f"Extensión objetivo: unas {target_words(pages, opts.nivel)} palabras."
    )
    return LLMRequest(
        system=system_for("analyze_chunk", opts),
        content=[header, chunk.text],
        schema=schemas.ChunkAnalysis,
        max_tokens=CHUNK_MAX_TOKENS,
        context={"paginas": (chunk.start_page, chunk.end_page)},
    )


def chapter_request(
    opts: StudyOptions,
    chapter: Chapter,
    analyses: list[schemas.ChunkAnalysis],
    exam_note: str = "",
) -> LLMRequest:
    """Petición de la etapa reduce para un capítulo (``exam_note``: lo que ha caído)."""
    header = (
        f"Capítulo: {chapter.title}\n"
        f"Páginas: {chapter.start_page}–{chapter.end_page} ({chapter.pages} páginas).\n"
        f"Extensión objetivo del capítulo: unas {target_words(chapter.pages, opts.nivel)} palabras."
        "\n\nAnálisis de los fragmentos (JSON):"
    )
    return LLMRequest(
        system=system_for("synthesize_chapter", opts),
        content=[
            header,
            *([exam_note] if exam_note else []),
            dumps([a.model_dump() for a in analyses]),
        ],
        schema=schemas.SintesisCapitulo,
        max_tokens=CHAPTER_MAX_TOKENS,
        context={"paginas": (chapter.start_page, chapter.end_page)},
    )


def book_request(opts: StudyOptions, chapters: list[schemas.Capitulo]) -> LLMRequest:
    """Petición final: mapa del libro y conexiones."""
    data = [
        {
            "titulo": c.titulo,
            "paginas": list(c.paginas),
            "prioridad": c.prioridad,
            "resumen": c.resumen,
            "imprescindibles": [k.titulo for k in c.conceptos if k.importancia == 3],  # noqa: PLR2004
        }
        for c in chapters
    ]
    return LLMRequest(
        system=system_for("synthesize_book", opts),
        content=["Capítulos del libro (JSON):", dumps(data)],
        schema=schemas.SintesisLibro,
        max_tokens=BOOK_MAX_TOKENS,
    )


_PRIORITY_UP: dict[schemas.Prioridad, schemas.Prioridad] = {
    "baja": "media",
    "media": "alta",
    "alta": "alta",
}


def raise_priority(prioridad: schemas.Prioridad) -> schemas.Prioridad:
    """Un nivel más de prioridad (lo que ha caído en examen sube)."""
    return _PRIORITY_UP[prioridad]


def _priority(prioridad: schemas.Prioridad, exam_topics: list[str]) -> schemas.Prioridad:
    return raise_priority(prioridad) if exam_topics else prioridad


def to_capitulo(
    chapter: Chapter, s: schemas.SintesisCapitulo, exam_topics: list[str] | None = None
) -> schemas.Capitulo:
    """Capítulo final a partir de la síntesis (``exam_topics``: temas que han caído)."""
    exam_topics = exam_topics or []
    return schemas.Capitulo(
        titulo=chapter.title,
        paginas=(chapter.start_page, chapter.end_page),
        prioridad=_priority(s.prioridad, exam_topics),
        resumen=s.resumen,
        esquema=s.esquema,
        conceptos=s.conceptos,
        preguntas=s.preguntas,
        paja=s.paja,
        ha_caido_en_examen=bool(exam_topics),
        temas_examen=exam_topics,
    )


def local_capitulo(
    chapter: Chapter, analyses: list[schemas.ChunkAnalysis], exam_topics: list[str] | None = None
) -> schemas.Capitulo:
    """Capítulo montado sin IA si la síntesis falla: une los fragmentos tal cual."""
    exam_topics = exam_topics or []
    seen: set[str] = set()
    conceptos: list[schemas.Concepto] = []
    for a in analyses:
        for c in a.conceptos:
            if c.titulo.lower() not in seen:
                seen.add(c.titulo.lower())
                conceptos.append(c)
    conceptos.sort(key=lambda c: -c.importancia)
    esquema = [
        schemas.NodoEsquema(texto=c.titulo, negrita=[], paginas=c.paginas, hijos=[])
        for c in conceptos
        if c.importancia == 3  # noqa: PLR2004
    ]
    imprescindibles = len(esquema)
    return schemas.Capitulo(
        titulo=chapter.title,
        paginas=(chapter.start_page, chapter.end_page),
        prioridad=_priority("alta" if imprescindibles >= 5 else "media", exam_topics),  # noqa: PLR2004
        resumen=" ".join(c.explicacion for c in conceptos[:3]),
        esquema=esquema,
        conceptos=conceptos,
        preguntas=[q for a in analyses for q in a.preguntas],
        paja=list(dict.fromkeys(p for a in analyses for p in a.paja)),
        ha_caido_en_examen=bool(exam_topics),
        temas_examen=exam_topics,
    )
