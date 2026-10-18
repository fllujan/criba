"""Detección de capítulos y fragmentación del texto (etapa 4 del spec §6).

Capítulos (RF-04): primero el índice interno del PDF; si no hay, títulos por tamaño
de letra (≥ 1,3 veces la mediana); si tampoco, bloques de 20 páginas.

Fragmentos: como máximo 12.000 tokens, cortando siempre entre párrafos y con 300
tokens de solapamiento con el fragmento anterior. Solo un párrafo que por sí solo
no cabe se divide, y siempre por frases.
"""

import hashlib
import re
import statistics
from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from criba.core.cost import estimate_tokens
from criba.core.ingest import Book, Paragraph, TocEntry

MAX_CHUNK_TOKENS = 12_000
OVERLAP_TOKENS = 300
BLOCK_PAGES = 20
HEADING_RATIO = 1.3
MAX_HEADING_CHARS = 120
SIZE_TOLERANCE = 0.5
PRELIMINARES = "Preliminares"
_OVERLAP_HEADER = "[Contexto: final del fragmento anterior]\n…"
_RESERVED_TOKENS = 40  # cabecera del solapamiento y marcas de página
_SENTENCE_END = re.compile(r"(?<=[.!?;:])\s+")

Source = Literal["toc", "fonts", "blocks"]


@dataclass(frozen=True, slots=True)
class Section:
    """Apartado dentro de un capítulo."""

    title: str
    level: int
    page: int


@dataclass(slots=True)
class Chapter:
    """Capítulo con su rango de páginas (ambos incluidos)."""

    title: str
    start_page: int
    end_page: int
    sections: list[Section]
    source: Source

    @property
    def pages(self) -> int:
        """Número de páginas del capítulo."""
        return self.end_page - self.start_page + 1


@dataclass(frozen=True, slots=True)
class PagedParagraph:
    """Párrafo con la página del libro de la que sale."""

    page: int
    text: str


@dataclass(frozen=True, slots=True)
class Chunk:
    """Fragmento que se envía a la IA en una llamada."""

    id: str
    chapter_title: str
    index: int
    paragraphs: tuple[PagedParagraph, ...]
    overlap: str
    text: str
    tokens: int

    @property
    def start_page(self) -> int:
        """Primera página del fragmento."""
        return self.paragraphs[0].page

    @property
    def end_page(self) -> int:
        """Última página del fragmento."""
        return self.paragraphs[-1].page


# --- Capítulos ------------------------------------------------------------------


def _ranges(starts: list[tuple[str, int]], page_count: int, source: Source) -> list[Chapter]:
    """Convierte (título, página inicial) en capítulos que cubren el libro."""
    starts = sorted(starts, key=lambda s: s[1])
    chapters: list[Chapter] = []
    if starts[0][1] > 1:
        chapters.append(Chapter(PRELIMINARES, 1, starts[0][1] - 1, [], source))
    for i, (title, start) in enumerate(starts):
        nxt = starts[i + 1][1] if i + 1 < len(starts) else page_count + 1
        chapters.append(Chapter(title, start, max(start, nxt - 1), [], source))
    return chapters


def _attach_sections(chapters: list[Chapter], sections: list[Section]) -> None:
    for sec in sections:
        for ch in chapters:
            if ch.start_page <= sec.page <= ch.end_page:
                ch.sections.append(sec)
                break


def _from_toc(toc: list[TocEntry], page_count: int) -> list[Chapter] | None:
    entries = [(lv, t.strip(), pg) for lv, t, pg in toc if 1 <= pg <= page_count and t.strip()]
    levels = sorted({lv for lv, _, _ in entries})
    level = next((lv for lv in levels if sum(1 for e in entries if e[0] == lv) >= 2), None)  # noqa: PLR2004
    if level is None:
        return None
    chapters = _ranges([(t, pg) for lv, t, pg in entries if lv == level], page_count, "toc")
    _attach_sections(chapters, [Section(t, 2, pg) for lv, t, pg in entries if lv == level + 1])
    return chapters


def _heading(par: Paragraph, threshold: float) -> float | None:
    """Tamaño de letra si el párrafo parece un título, si no ``None``."""
    sizes = [ln.size for ln in par.lines]
    text = par.text
    if (
        min(sizes) >= threshold
        and max(sizes) - min(sizes) <= SIZE_TOLERANCE
        and len(text) <= MAX_HEADING_CHARS
        and any(c.isalpha() for c in text)
    ):
        return round(sizes[0] * 2) / 2
    return None


def _from_fonts(book: Book) -> list[Chapter] | None:
    weighted = [
        ln.size
        for pg in book.pages
        for par in pg.paragraphs
        for ln in par.lines
        for _ in range(max(1, len(ln.text) // 10))
    ]
    if not weighted:
        return None
    threshold = HEADING_RATIO * statistics.median(weighted)
    found: list[tuple[float, str, int]] = []
    for page in book.pages:
        for par in page.paragraphs:
            size = _heading(par, threshold)
            if size is not None:
                found.append((size, par.text, page.number))
    pages_by_size: dict[float, set[int]] = defaultdict(set)
    for size, _, page_no in found:
        pages_by_size[size].add(page_no)
    sizes = sorted(pages_by_size, reverse=True)
    chapter_size = next((s for s in sizes if len(pages_by_size[s]) >= 2), None)  # noqa: PLR2004
    if chapter_size is None:
        return None
    starts: list[tuple[str, int]] = []
    seen_pages: set[int] = set()
    for size, text, page_no in found:
        if size == chapter_size and page_no not in seen_pages:
            starts.append((text, page_no))
            seen_pages.add(page_no)
    chapters = _ranges(starts, len(book.pages), "fonts")
    smaller = [s for s in sizes if s < chapter_size]
    if smaller:
        _attach_sections(chapters, [Section(t, 2, pg) for s, t, pg in found if s == smaller[0]])
    return chapters


def _from_blocks(page_count: int) -> list[Chapter]:
    return [
        Chapter(
            f"Páginas {start}–{min(start + BLOCK_PAGES - 1, page_count)}",
            start,
            min(start + BLOCK_PAGES - 1, page_count),
            [],
            "blocks",
        )
        for start in range(1, page_count + 1, BLOCK_PAGES)
    ]


def detect_chapters(book: Book) -> list[Chapter]:
    """Detecta los capítulos del libro (RF-04). Siempre cubren todas las páginas."""
    page_count = len(book.pages)
    return _from_toc(book.toc, page_count) or _from_fonts(book) or _from_blocks(page_count)


def chapter_paragraphs(book: Book, chapter: Chapter) -> list[PagedParagraph]:
    """Párrafos del capítulo con su página."""
    return [
        PagedParagraph(page.number, par.text)
        for page in book.pages[chapter.start_page - 1 : chapter.end_page]
        for par in page.paragraphs
        if par.text.strip()
    ]


# --- Fragmentación ----------------------------------------------------------------


def _render(paragraphs: list[PagedParagraph], overlap: str) -> str:
    parts: list[str] = []
    if overlap:
        parts.append(_OVERLAP_HEADER + overlap)
    page: int | None = None
    for par in paragraphs:
        if par.page != page:
            parts.append(f"[p. {par.page}]\n{par.text}")
            page = par.page
        else:
            parts.append(par.text)
    return "\n\n".join(parts)


def _split_words(text: str, budget: int) -> list[str]:
    words = text.split(" ")
    pieces: list[str] = []
    current: list[str] = []
    for word in words:
        if current and estimate_tokens(" ".join([*current, word])) > budget:
            pieces.append(" ".join(current))
            current = []
        current.append(word)
    if current:
        pieces.append(" ".join(current))
    return pieces


def _split_paragraph(par: PagedParagraph, budget: int) -> list[PagedParagraph]:
    """Divide por frases un párrafo que por sí solo supera ``budget`` tokens."""
    if estimate_tokens(par.text) <= budget:
        return [par]
    sentences: list[str] = []
    for sentence in _SENTENCE_END.split(par.text):
        sentences.extend(
            [sentence] if estimate_tokens(sentence) <= budget else _split_words(sentence, budget)
        )
    pieces: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}" if current else sentence
        if current and estimate_tokens(candidate) > budget:
            pieces.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        pieces.append(current)
    return [PagedParagraph(par.page, p) for p in pieces]


def _tail(paragraphs: list[PagedParagraph], limit: int) -> str:
    """Últimas frases del fragmento que caben en ``limit`` tokens."""
    if limit <= 0 or not paragraphs:
        return ""
    sentences = [s for p in paragraphs for s in _SENTENCE_END.split(p.text)]
    tail = ""
    for sentence in reversed(sentences):
        candidate = f"{sentence} {tail}" if tail else sentence
        if estimate_tokens("…" + candidate) > limit:
            break
        tail = candidate
    if not tail:
        words = sentences[-1].split(" ")
        while words and estimate_tokens("…" + " ".join(words)) > limit:
            words.pop(0)
        tail = " ".join(words)
    return tail


def _make_chunk(
    chapter: Chapter, index: int, paragraphs: list[PagedParagraph], overlap: str
) -> Chunk:
    text = _render(paragraphs, overlap)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return Chunk(
        id=f"p{paragraphs[0].page}-{digest}",
        chapter_title=chapter.title,
        index=index,
        paragraphs=tuple(paragraphs),
        overlap=overlap,
        text=text,
        tokens=estimate_tokens(text),
    )


def chunk_chapter(
    book: Book,
    chapter: Chapter,
    max_tokens: int = MAX_CHUNK_TOKENS,
    overlap_tokens: int = OVERLAP_TOKENS,
) -> list[Chunk]:
    """Divide el capítulo en fragmentos de como máximo ``max_tokens`` tokens."""
    budget = max_tokens - overlap_tokens - _RESERVED_TOKENS
    pieces = [
        piece
        for par in chapter_paragraphs(book, chapter)
        for piece in _split_paragraph(par, budget)
    ]
    chunks: list[Chunk] = []
    current: list[PagedParagraph] = []
    overlap = ""
    for piece in pieces:
        if not current or estimate_tokens(_render([*current, piece], overlap)) <= max_tokens:
            current.append(piece)
            continue
        chunks.append(_make_chunk(chapter, len(chunks), current, overlap))
        overlap = _tail(current, overlap_tokens)
        current = [piece]
    if current:
        chunks.append(_make_chunk(chapter, len(chunks), current, overlap))
    return chunks
