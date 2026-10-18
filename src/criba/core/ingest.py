"""Validación del PDF y extracción de texto por página (etapas 1 y 2 del spec §6).

Se procesa página a página para no cargar el libro entero en memoria (RNF-02):
del PDF solo se guarda el texto, el tamaño de letra y la negrita de cada línea.
"""

import hashlib
import logging
import re
from collections import Counter, defaultdict
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
REPEAT_WINDOW = 6  # cabeceras que cambian por capítulo: ≥3 veces en 6 páginas seguidas
REPEAT_IN_WINDOW = 3
NARROW_BLOCK = 0.55  # bloque más estrecho que esto (fracción del ancho) = columna
OCR_SIZE = 0.0  # tamaño de letra «desconocido» de las líneas que vienen del OCR
_BOLD_FLAG = 16
_TEXT_FLAGS = pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_PRESERVE_IMAGES
_ROMAN = r"(?=[ivxlcdm])m{0,3}(?:cm|cd|d?c{0,3})(?:xc|xl|l?x{0,3})(?:ix|iv|v?i{0,3})"
_PAGE_NUMBER = re.compile(
    rf"^[\W_]*(?:p[áa]g(?:ina)?\.?\s*)?(?:\d{{1,4}}|{_ROMAN})[\W_]*$", re.IGNORECASE
)
_HYPHENS = ("-", "\u00ad", "\u2010")
_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")
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
            out = join_text(out, line.text.strip())
        return out.replace("\u00ad", "")


def join_text(left: str, right: str) -> str:
    """Une dos trozos de texto; si ``left`` acaba en guion de corte, une la palabra."""
    if not left:
        return right
    if left.endswith(_HYPHENS) and right[:1].islower():
        return left[:-1] + right
    return f"{left} {right}"


@dataclass(slots=True)
class Page:
    """Una página del libro (numeradas desde 1)."""

    number: int
    paragraphs: list[Paragraph]
    has_images: bool
    ocr: bool = False

    def set_ocr_text(self, text: str) -> None:
        """Sustituye el contenido por el texto del OCR (párrafos separados por línea en blanco)."""
        self.paragraphs = [
            Paragraph([Line(chunk.strip(), OCR_SIZE, False)])
            for chunk in _PARAGRAPH_BREAK.split(text)
            if chunk.strip()
        ]
        self.ocr = True

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
        return not self.ocr and self.has_images and self.useful_chars < SCANNED_MIN_CHARS


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

    @property
    def ocr_pages(self) -> list[int]:
        """Números de las páginas cuyo texto viene del OCR."""
        return [p.number for p in self.pages if p.ocr]


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


def _split_columns(block: dict[str, Any], width: float) -> list[dict[str, Any]]:
    """Separa un bloque que MuPDF ha formado con líneas de dos columnas."""
    lines = block["lines"]
    narrow = all((ln["bbox"][2] - ln["bbox"][0]) < NARROW_BLOCK * width for ln in lines)
    if not narrow:
        return [block]
    left = [ln for ln in lines if (ln["bbox"][0] + ln["bbox"][2]) / 2 < width / 2]
    right = [ln for ln in lines if (ln["bbox"][0] + ln["bbox"][2]) / 2 >= width / 2]
    if not left or not right:
        return [block]

    def sub(group: list[dict[str, Any]]) -> dict[str, Any]:
        bbox = (
            min(ln["bbox"][0] for ln in group),
            min(ln["bbox"][1] for ln in group),
            max(ln["bbox"][2] for ln in group),
            max(ln["bbox"][3] for ln in group),
        )
        return {**block, "lines": group, "bbox": bbox}

    return [sub(left), sub(right)]


def _reading_order(
    blocks: list[dict[str, Any]], width: float, height: float
) -> list[dict[str, Any]]:
    """Ordena los bloques como se leen: en páginas a dos columnas, primero la izquierda.

    Los bloques estrechos consecutivos forman una zona de columnas que se lee por
    columna y luego de arriba abajo; un bloque ancho, o una cabecera o pie, corta la zona.
    """

    def is_column(b: dict[str, Any]) -> bool:
        x0, y0, x1, y1 = b["bbox"]
        in_edge = y1 / height < EDGE_ZONE or y0 / height > 1 - EDGE_ZONE
        return not in_edge and (x1 - x0) < NARROW_BLOCK * width

    def column(b: dict[str, Any]) -> int:
        x0, _, x1, _ = b["bbox"]
        return 0 if (x0 + x1) / 2 < width / 2 else 1

    ordered: list[dict[str, Any]] = []
    run: list[dict[str, Any]] = []
    for block in sorted(blocks, key=lambda b: (b["bbox"][1], b["bbox"][0])):
        if is_column(block):
            run.append(block)
            continue
        ordered.extend(sorted(run, key=lambda b: (column(b), b["bbox"][1])))
        run = []
        ordered.append(block)
    ordered.extend(sorted(run, key=lambda b: (column(b), b["bbox"][1])))
    return ordered


def _extract_page(page: pymupdf.Page, number: int) -> Page:
    height = float(page.rect.height) or 1.0
    width = float(page.rect.width) or 1.0
    data: dict[str, Any] = page.get_text("dict", flags=_TEXT_FLAGS)
    text_blocks = [
        part for b in data["blocks"] if b.get("type") == 0 for part in _split_columns(b, width)
    ]
    paragraphs: list[Paragraph] = []
    for block in _reading_order(text_blocks, width, height):
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


def _outermost(page: Page) -> set[int]:
    """``id`` de las líneas más externas de la franja superior y de la inferior."""
    edge = [ln for par in page.paragraphs for ln in par.lines if _is_edge(ln)]
    top = [ln for ln in edge if ln.y < EDGE_ZONE]
    bottom = [ln for ln in edge if ln.y > 1 - EDGE_ZONE]
    out: set[int] = set()
    if top:
        y = min(ln.y for ln in top)
        out |= {id(ln) for ln in top if ln.y - y < 0.015}  # noqa: PLR2004
    if bottom:
        y = max(ln.y for ln in bottom)
        out |= {id(ln) for ln in bottom if y - ln.y < 0.015}  # noqa: PLR2004
    return out


def clean_headers_footers(pages: list[Page]) -> None:
    """Quita números de página y cabeceras/pies repetidos (en sitio).

    Solo se miran las líneas de la franja superior e inferior. Con los números
    normalizados, una línea es cabecera o pie si aparece en más del 50 % de las
    páginas con texto, en más del 50 % de las pares o de las impares (cabeceras
    alternas), o al menos 3 veces en 6 páginas seguidas (cabeceras que cambian con
    cada capítulo). Un número de página solo se quita si es la línea más externa.
    """
    text_pages = [p for p in pages if p.paragraphs]
    counts: Counter[str] = Counter()
    by_parity: dict[int, Counter[str]] = {0: Counter(), 1: Counter()}
    positions: dict[str, list[int]] = defaultdict(list)
    for index, page in enumerate(text_pages):
        keys = {_normalize(ln.text) for par in page.paragraphs for ln in par.lines if _is_edge(ln)}
        counts.update(keys)
        by_parity[page.number % 2].update(keys)
        for key in keys:
            positions[key].append(index)
    parity_totals = {k: sum(1 for p in text_pages if p.number % 2 == k) for k in (0, 1)}
    enough_pages = len(text_pages) >= MIN_PAGES_FOR_REPEATS

    def in_window(key: str) -> bool:
        pos = positions[key]
        span = REPEAT_IN_WINDOW - 1
        return any(pos[i + span] - pos[i] < REPEAT_WINDOW for i in range(len(pos) - span))

    def repeated(key: str) -> bool:
        if not enough_pages:
            return False
        if counts[key] > REPEAT_RATIO * len(text_pages) or in_window(key):
            return True
        return any(
            parity_totals[k] >= 2 and by_parity[k][key] > REPEAT_RATIO * parity_totals[k]  # noqa: PLR2004
            for k in (0, 1)
        )

    for page in pages:
        outer = _outermost(page)

        def drop(ln: Line, outer: set[int] = outer) -> bool:
            if not _is_edge(ln):
                return False
            if id(ln) in outer and _PAGE_NUMBER.match(ln.text.strip()):
                return True
            return repeated(_normalize(ln.text))

        kept: list[Paragraph] = []
        for par in page.paragraphs:
            lines = [ln for ln in par.lines if not drop(ln)]
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


_STOPWORDS: dict[str, frozenset[str]] = {
    "es": frozenset(
        "el la los las de del que y en un una por con para es se no al lo como".split()
    ),
    "en": frozenset("the of and to in is that for with as are by this be it on from".split()),
    "fr": frozenset("le la les des est et une dans pour que qui du au sur pas ce".split()),
    "pt": frozenset("o os as de que não uma para com do da em um por mais dos".split()),
    "it": frozenset("il di che è per non sono del della un una gli nel con le".split()),
    "de": frozenset("der die das und ist nicht mit ein eine zu den von sich auf für".split()),
    "ca": frozenset("el la els les de que i en un una per amb és del al dels no".split()),
}
_WORD = re.compile(r"[a-zà-ÿ]+")


def detect_language(book: Book, sample_chars: int = 60_000) -> str:
    """Idioma del libro por palabras frecuentes. Devuelve un código (``es``, ``en``…)."""
    sample: list[str] = []
    size = 0
    for page in book.pages:
        if size >= sample_chars:
            break
        text = page.text.lower()
        sample.append(text)
        size += len(text)
    words = _WORD.findall(" ".join(sample))
    if not words:
        return "es"
    scores = {lang: sum(1 for w in words if w in stop) for lang, stop in _STOPWORDS.items()}
    return max(scores, key=lambda lang: scores[lang])
