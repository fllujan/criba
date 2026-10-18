"""Validación del PDF y extracción de texto por página (etapas 1 y 2 del spec §6).

Se procesa página a página para no cargar el libro entero en memoria (RNF-02):
del PDF solo se guarda el texto, el tamaño de letra y la negrita de cada línea.
"""

import hashlib
import logging
import re
from collections import Counter
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pymupdf

from criba.core.errors import CribaError, ErrorKind

log = logging.getLogger(__name__)

MAX_PAGES = 1500
MAX_BYTES = 500 * 1024 * 1024
SCANNED_MIN_CHARS = 80
EDGE_ZONE = 0.12  # franja superior/inferior (fracción de la altura) de cabeceras y pies
REPEAT_RATIO = 0.5
MIN_PAGES_FOR_REPEATS = 4
_BOLD_FLAG = 16
_TEXT_FLAGS = pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES
_PAGE_NUMBER = re.compile(
    r"^[\W_]*(p[áa]g(ina)?\.?\s*)?(\d{1,4}|[ivxlcdm]{1,7})[\W_]*$", re.IGNORECASE
)
_DIGITS = re.compile(r"\d+")
_SPACES = re.compile(r"\s+")

OnPage = Callable[[int, int], None]


@dataclass(frozen=True, slots=True)
class Line:
    """Una línea de texto con su tamaño de letra y si es negrita."""

    text: str
    size: float
    bold: bool
    y: float = 0.5  # posición vertical relativa (0 = arriba, 1 = abajo)


@dataclass(slots=True)
class Paragraph:
    """Bloque de texto (≈ párrafo o título)."""

    lines: list[Line]

    @property
    def text(self) -> str:
        """Texto del párrafo, uniendo las palabras cortadas con guion."""
        out = ""
        for line in self.lines:
            t = line.text.strip()
            if not out:
                out = t
            elif out.endswith("-") and t[:1].islower():
                out = out[:-1] + t
            else:
                out = f"{out} {t}"
        return out


@dataclass(slots=True)
class Page:
    """Una página del libro (numeradas desde 1)."""

    number: int
    paragraphs: list[Paragraph]
    has_images: bool

    @property
    def text(self) -> str:
        """Texto de la página, un párrafo por bloque."""
        return "\n\n".join(p.text for p in self.paragraphs)

    @property
    def useful_chars(self) -> int:
        """Caracteres que no son espacios."""
        return sum(len(_SPACES.sub("", p.text)) for p in self.paragraphs)

    @property
    def is_scanned(self) -> bool:
        """Sin texto útil pero con imágenes: se leerá con la visión de Claude."""
        return self.has_images and self.useful_chars < SCANNED_MIN_CHARS


@dataclass(frozen=True, slots=True)
class PdfInfo:
    """Datos básicos del PDF validado."""

    path: Path
    sha256: str
    page_count: int
    title: str
    size_bytes: int
    has_toc: bool


TocEntry = tuple[int, str, int]  # (nivel, título, página)


@dataclass(slots=True)
class Book:
    """Libro extraído y limpio."""

    info: PdfInfo
    pages: list[Page]
    toc: list[TocEntry] = field(default_factory=list)

    @property
    def scanned_pages(self) -> list[int]:
        """Números de las páginas escaneadas."""
        return [p.number for p in self.pages if p.is_scanned]


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    """Hash SHA-256 del archivo, leído por trozos."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


@contextmanager
def _open_pdf(path: Path) -> Iterator[pymupdf.Document]:
    if not path.is_file():
        raise CribaError(ErrorKind.NOT_FOUND, detail=str(path))
    size = path.stat().st_size
    if size > MAX_BYTES:
        raise CribaError(ErrorKind.TOO_LARGE, detail=f"{size} bytes")
    try:
        doc = pymupdf.open(path, filetype="pdf")
    except (pymupdf.FileDataError, RuntimeError, ValueError) as exc:
        raise CribaError(ErrorKind.CORRUPT, detail=repr(exc)) from exc
    try:
        if doc.needs_pass:
            raise CribaError(ErrorKind.PASSWORD_PROTECTED, detail=str(path))
        if not doc.is_pdf or doc.page_count == 0:
            raise CribaError(ErrorKind.CORRUPT, detail="sin páginas o no es PDF")
        if doc.page_count > MAX_PAGES:
            raise CribaError(ErrorKind.TOO_MANY_PAGES, detail=f"{doc.page_count} páginas")
        yield doc
    finally:
        doc.close()


def _info(path: Path, doc: pymupdf.Document) -> PdfInfo:
    meta: dict[str, str] = doc.metadata or {}
    title = (meta.get("title") or "").strip() or path.stem
    return PdfInfo(
        path=path,
        sha256=sha256_file(path),
        page_count=int(doc.page_count),
        title=title,
        size_bytes=path.stat().st_size,
        has_toc=bool(doc.get_toc()),
    )


def validate(path: Path) -> PdfInfo:
    """Valida el PDF (RF-02) sin extraer el texto. Lanza ``CribaError`` si falla."""
    with _open_pdf(path) as doc:
        return _info(path, doc)


def _extract_page(page: pymupdf.Page, number: int) -> Page:
    height = float(page.rect.height) or 1.0
    data: dict[str, Any] = page.get_text("dict", sort=True, flags=_TEXT_FLAGS)
    paragraphs: list[Paragraph] = []
    for block in data["blocks"]:
        if block.get("type") != 0:
            continue
        lines: list[Line] = []
        for raw in block["lines"]:
            spans = [s for s in raw["spans"] if s["text"].strip()]
            if not spans:
                continue
            text = "".join(s["text"] for s in spans).strip()
            main = max(spans, key=lambda s: len(s["text"]))
            bold_chars = sum(
                len(s["text"])
                for s in spans
                if s["flags"] & _BOLD_FLAG or "bold" in s["font"].lower()
            )
            y0, y1 = raw["bbox"][1], raw["bbox"][3]
            lines.append(
                Line(
                    text=text,
                    size=round(float(main["size"]), 2),
                    bold=bold_chars * 2 > len(text),
                    y=((y0 + y1) / 2) / height,
                )
            )
        if lines:
            paragraphs.append(Paragraph(lines))
    return Page(number=number, paragraphs=paragraphs, has_images=bool(page.get_images()))


def _normalize(text: str) -> str:
    return _SPACES.sub(" ", _DIGITS.sub("#", text.lower())).strip()


def _is_edge(line: Line) -> bool:
    return line.y < EDGE_ZONE or line.y > 1 - EDGE_ZONE


def clean_headers_footers(pages: list[Page]) -> None:
    """Quita números de página y cabeceras/pies repetidos (en sitio).

    Una línea de la franja superior o inferior se considera repetida si, con los
    números normalizados, aparece en más del 50 % de las páginas con texto, o en
    más del 50 % de las pares o de las impares (cabeceras alternas de los libros).
    """
    text_pages = [p for p in pages if p.paragraphs]
    counts: Counter[str] = Counter()
    by_parity: dict[int, Counter[str]] = {0: Counter(), 1: Counter()}
    for page in text_pages:
        keys = {_normalize(ln.text) for par in page.paragraphs for ln in par.lines if _is_edge(ln)}
        counts.update(keys)
        by_parity[page.number % 2].update(keys)
    parity_totals = {k: sum(1 for p in text_pages if p.number % 2 == k) for k in (0, 1)}

    def repeated(key: str) -> bool:
        if len(text_pages) < MIN_PAGES_FOR_REPEATS:
            return False
        if counts[key] > REPEAT_RATIO * len(text_pages):
            return True
        return any(
            parity_totals[k] >= 2 and by_parity[k][key] > REPEAT_RATIO * parity_totals[k]  # noqa: PLR2004
            for k in (0, 1)
        )

    for page in pages:
        kept: list[Paragraph] = []
        for par in page.paragraphs:
            lines = [
                ln
                for ln in par.lines
                if not (
                    _is_edge(ln)
                    and (_PAGE_NUMBER.match(ln.text.strip()) or repeated(_normalize(ln.text)))
                )
            ]
            if lines:
                kept.append(Paragraph(lines))
        page.paragraphs = kept


def open_book(path: Path, on_page: OnPage | None = None) -> Book:
    """Valida, extrae y limpia el libro. ``on_page(hechas, total)`` informa del avance."""
    with _open_pdf(path) as doc:
        info = _info(path, doc)
        pages: list[Page] = []
        for i in range(info.page_count):
            pages.append(_extract_page(doc[i], i + 1))
            if on_page:
                on_page(i + 1, info.page_count)
        toc: list[TocEntry] = [(int(lv), str(t), int(pg)) for lv, t, pg, *_ in doc.get_toc()]
    clean_headers_footers(pages)
    book = Book(info=info, pages=pages, toc=toc)
    if not book.scanned_pages and sum(p.useful_chars for p in pages) < SCANNED_MIN_CHARS:
        raise CribaError(ErrorKind.NO_TEXT, detail=str(path))
    log.info(
        "Libro leído: %d páginas, %d escaneadas, índice=%s",
        info.page_count,
        len(book.scanned_pages),
        info.has_toc,
    )
    return book
