"""Piezas comunes de los dos PDF: plantilla A4, marcadores, enlaces y recuadros.

El documento se genera en dos pasadas: la primera averigua en qué página cae cada
capítulo y la segunda escribe el índice con esos números (y enlaces internos).
"""

import io
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from reportlab.lib.colors import Color
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    PageTemplate,
    Paragraph,
    Table,
    TableStyle,
)
from reportlab.platypus.flowables import KeepTogether

from criba import __version__
from criba.render.styles import (
    ACCENT,
    BOX_BG,
    MARGIN,
    MUTED,
    PAGE_SIZE,
    RULE,
    SANS,
    TEXT,
    register_fonts,
)

PageMap = dict[str, int]
CONTENT_WIDTH = PAGE_SIZE[0] - 2 * MARGIN


class Heading(Paragraph):  # type: ignore[misc]
    """Título que crea un marcador (índice lateral) y un destino para enlaces.

    Acepta los argumentos de ``Paragraph`` porque ReportLab crea la continuación
    con el mismo constructor cuando un título larguísimo se parte entre páginas.
    """

    def __init__(
        self,
        text: str,
        style: ParagraphStyle,
        *args: object,
        key: str = "",
        outline: str = "",
        level: int = 0,
        **kwargs: object,
    ) -> None:
        super().__init__(text, style, *args, **kwargs)
        self.key = key
        self.outline = outline
        self.level = level

    def split(self, avail_width: float, avail_height: float) -> list[Flowable]:
        """Parte el título conservando el marcador en la primera parte."""
        parts: list[Flowable] = super().split(avail_width, avail_height)
        if parts and isinstance(parts[0], Heading):
            parts[0].key, parts[0].outline, parts[0].level = self.key, self.outline, self.level
        return parts


class CheckBox(Flowable):  # type: ignore[misc]
    """Casilla vacía para marcar a mano (se dibuja: no depende de la fuente)."""

    def __init__(self, size: float = 9) -> None:
        super().__init__()
        self.size = size

    def wrap(self, avail_width: float, avail_height: float) -> tuple[float, float]:
        """Tamaño de la casilla."""
        return self.size + 2, self.size + 3

    def draw(self) -> None:
        """Dibuja el cuadrado."""
        self.canv.setStrokeColor(TEXT)
        self.canv.setLineWidth(0.8)
        self.canv.rect(1, 1, self.size, self.size)


class CribaDoc(BaseDocTemplate):  # type: ignore[misc]
    """A4 con márgenes de 2 cm, portada sin pie y pie con número de página."""

    def __init__(self, target: str | io.BytesIO, *, title: str, footer: str, subject: str) -> None:
        super().__init__(
            target,
            pagesize=PAGE_SIZE,
            leftMargin=MARGIN,
            rightMargin=MARGIN,
            topMargin=MARGIN,
            bottomMargin=MARGIN,
            title=title,
            author="Criba",
            subject=subject,
            creator=f"Criba {__version__}",
        )
        self.footer = footer
        self.page_map: PageMap = {}
        frame = Frame(
            MARGIN,
            MARGIN,
            CONTENT_WIDTH,
            PAGE_SIZE[1] - 2 * MARGIN,
            id="body",
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        )
        self.addPageTemplates(
            [
                PageTemplate(id="cover", frames=[frame], onPage=self._cover),
                PageTemplate(id="normal", frames=[frame], onPage=self._decorate),
            ]
        )

    def _cover(self, canvas: Canvas, doc: object) -> None:
        canvas.saveState()
        canvas.setFillColor(ACCENT)
        canvas.rect(0, PAGE_SIZE[1] - 0.6 * MARGIN, PAGE_SIZE[0], 0.6 * MARGIN, stroke=0, fill=1)
        canvas.restoreState()

    def _decorate(self, canvas: Canvas, doc: BaseDocTemplate) -> None:
        canvas.saveState()
        y = MARGIN * 0.55
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, y + 11, PAGE_SIZE[0] - MARGIN, y + 11)
        canvas.setFont(SANS, 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(MARGIN, y, fit_text(self.footer, SANS, 8, CONTENT_WIDTH - 40))
        canvas.drawRightString(PAGE_SIZE[0] - MARGIN, y, str(doc.page))
        canvas.restoreState()

    def afterFlowable(self, flowable: Flowable) -> None:  # noqa: N802 (API de ReportLab)
        """Crea el marcador y apunta la página de cada título."""
        if isinstance(flowable, Heading) and flowable.key and flowable.key not in self.page_map:
            self.canv.bookmarkPage(flowable.key)
            self.canv.addOutlineEntry(
                flowable.outline, flowable.key, level=flowable.level, closed=flowable.level > 0
            )
            self.page_map[flowable.key] = self.page


def fit_text(text: str, font: str, size: float, width: float) -> str:
    """Recorta ``text`` con «…» para que quepa en ``width`` puntos."""
    if stringWidth(text, font, size) <= width:
        return text
    while text and stringWidth(text + "…", font, size) > width:
        text = text[:-1]
    return text.rstrip() + "…"


def build(
    target: Path,
    story_for: Callable[[PageMap], list[Flowable]],
    *,
    title: str,
    footer: str,
    subject: str,
) -> Path:
    """Genera el PDF en dos pasadas en ``target`` (ruta temporal: la confirma quien llama)."""
    register_fonts()
    first = CribaDoc(io.BytesIO(), title=title, footer=footer, subject=subject)
    first.build(story_for({}))
    pages = dict(first.page_map)
    doc = CribaDoc(str(target), title=title, footer=footer, subject=subject)
    doc.build(story_for(pages))
    return target


def box(
    content: Sequence[Flowable],
    *,
    background: Color = BOX_BG,
    border: Color | None = ACCENT,
    padding: float = 8,
) -> Flowable:
    """Recuadro con fondo suave y borde izquierdo de 3 pt (definiciones, fórmulas)."""
    table = Table([[list(content)]], colWidths=[CONTENT_WIDTH], splitInRow=1)
    commands: list[tuple[Any, ...]] = [
        ("BACKGROUND", (0, 0), (-1, -1), background),
        ("LEFTPADDING", (0, 0), (-1, -1), padding + 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), padding),
        ("TOPPADDING", (0, 0), (-1, -1), padding - 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), padding),
    ]
    if border is not None:
        commands.append(("LINEBEFORE", (0, 0), (0, -1), 3, border))
    table.setStyle(TableStyle(commands))
    return KeepTogether([table])
