"""Colores, fuentes, márgenes y textos de los PDF (spec §7).

Los PDF se imprimen bien en blanco y negro: la prioridad nunca va solo en color,
siempre también con texto (ALTA/MEDIA/BAJA) y puntos (●●●).
"""

from dataclasses import dataclass
from functools import cache
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONTS_DIR = Path(__file__).parent.parent / "assets" / "fonts"

PAGE_SIZE = A4
MARGIN = 2 * cm
BODY_SIZE = 10.5
LEADING = round(BODY_SIZE * 1.35, 2)
H1, H2, H3 = 20, 15, 12
REF_SIZE = 9

ACCENT = colors.HexColor("#6B8E23")
ACCENT_DARK = colors.HexColor("#4E6B17")
TEXT = colors.HexColor("#1F2318")
MUTED = colors.HexColor("#7F8C8D")
BOX_BG = colors.HexColor("#F4F7EC")
RULE = colors.HexColor("#D9DFCC")
PRIORITY_COLORS = {
    "alta": colors.HexColor("#C0392B"),
    "media": colors.HexColor("#D68910"),
    "baja": colors.HexColor("#7F8C8D"),
}
PRIORITY_DOTS = {"alta": "●●●", "media": "●●○", "baja": "●○○"}
STARS = {3: "★★★", 2: "★★", 1: "★"}

SANS = "Inter"
SANS_MEDIUM = "Inter-Medium"
SANS_SEMIBOLD = "Inter-SemiBold"
SERIF = "SourceSerif4"


@cache
def register_fonts() -> None:
    """Registra las fuentes incluidas en la app (una sola vez)."""
    files = {
        "Inter": "Inter-Regular.ttf",
        "Inter-Medium": "Inter-Medium.ttf",
        "Inter-SemiBold": "Inter-SemiBold.ttf",
        "Inter-Bold": "Inter-Bold.ttf",
        "Inter-Italic": "Inter-Italic.ttf",
        "SourceSerif4": "SourceSerif4-Regular.ttf",
        "SourceSerif4-Italic": "SourceSerif4-It.ttf",
        "SourceSerif4-Semibold": "SourceSerif4-Semibold.ttf",
        "SourceSerif4-Bold": "SourceSerif4-Bold.ttf",
        "SourceSerif4-BoldItalic": "SourceSerif4-BoldIt.ttf",
    }
    for name, file in files.items():
        pdfmetrics.registerFont(TTFont(name, str(FONTS_DIR / file)))
    pdfmetrics.registerFontFamily(
        "Inter",
        normal="Inter",
        bold="Inter-SemiBold",
        italic="Inter-Italic",
        boldItalic="Inter-Bold",
    )
    pdfmetrics.registerFontFamily(
        "SourceSerif4",
        normal="SourceSerif4",
        bold="SourceSerif4-Semibold",
        italic="SourceSerif4-Italic",
        boldItalic="SourceSerif4-BoldItalic",
    )


@dataclass(frozen=True, slots=True)
class Styles:
    """Estilos de párrafo de los dos PDF."""

    body: ParagraphStyle
    body_tight: ParagraphStyle
    lead: ParagraphStyle
    h1: ParagraphStyle
    h2: ParagraphStyle
    h3: ParagraphStyle
    meta: ParagraphStyle
    small: ParagraphStyle
    box_title: ParagraphStyle
    formula: ParagraphStyle
    quote: ParagraphStyle
    toc: ParagraphStyle
    toc_num: ParagraphStyle
    cover_title: ParagraphStyle
    cover_sub: ParagraphStyle
    cover_meta: ParagraphStyle
    table_head: ParagraphStyle
    table_cell: ParagraphStyle
    bullet: tuple[ParagraphStyle, ParagraphStyle, ParagraphStyle]


@cache
def styles() -> Styles:
    """Estilos con la tipografía del spec (§7, «Estilo»)."""
    register_fonts()
    body = ParagraphStyle(
        "body",
        fontName=SERIF,
        fontSize=BODY_SIZE,
        leading=LEADING,
        textColor=TEXT,
        spaceAfter=6,
    )
    sans = ParagraphStyle("sans", parent=body, fontName=SANS)
    bullets = tuple(
        ParagraphStyle(
            f"bullet{level}",
            parent=body,
            leftIndent=14 + level * 16,
            bulletIndent=2 + level * 16,
            spaceAfter=2 if level else 3,
            fontSize=BODY_SIZE - (0.5 * level),
            leading=LEADING - level,
            bulletFontName=SANS_SEMIBOLD,
            bulletColor=ACCENT if level == 0 else MUTED,
        )
        for level in range(3)
    )
    return Styles(
        body=body,
        body_tight=ParagraphStyle("tight", parent=body, spaceAfter=2),
        lead=ParagraphStyle(
            "lead", parent=body, fontSize=BODY_SIZE + 0.5, leading=LEADING + 1, spaceAfter=10
        ),
        h1=ParagraphStyle(
            "h1",
            parent=sans,
            fontName=SANS_SEMIBOLD,
            fontSize=H1,
            leading=H1 * 1.2,
            spaceBefore=0,
            spaceAfter=6,
            textColor=TEXT,
        ),
        h2=ParagraphStyle(
            "h2",
            parent=sans,
            fontName=SANS_SEMIBOLD,
            fontSize=H2,
            leading=H2 * 1.25,
            spaceBefore=14,
            spaceAfter=6,
        ),
        h3=ParagraphStyle(
            "h3",
            parent=sans,
            fontName=SANS_SEMIBOLD,
            fontSize=H3,
            leading=H3 * 1.3,
            spaceBefore=10,
            spaceAfter=4,
        ),
        meta=ParagraphStyle(
            "meta",
            parent=sans,
            fontName=SANS_MEDIUM,
            fontSize=9,
            leading=12,
            textColor=MUTED,
            spaceAfter=10,
        ),
        small=ParagraphStyle(
            "small", parent=sans, fontSize=REF_SIZE, leading=12, textColor=MUTED, spaceAfter=2
        ),
        box_title=ParagraphStyle(
            "box_title",
            parent=sans,
            fontName=SANS_SEMIBOLD,
            fontSize=BODY_SIZE,
            leading=LEADING,
            spaceAfter=2,
        ),
        formula=ParagraphStyle(
            "formula",
            parent=body,
            fontSize=BODY_SIZE + 2.5,
            leading=LEADING + 4,
            alignment=TA_CENTER,
            spaceAfter=2,
        ),
        quote=ParagraphStyle("quote", parent=body, fontName="SourceSerif4-Italic", spaceAfter=2),
        toc=ParagraphStyle("toc", parent=sans, fontSize=BODY_SIZE, leading=14),
        toc_num=ParagraphStyle(
            "toc_num",
            parent=sans,
            fontSize=BODY_SIZE,
            leading=14,
            alignment=TA_LEFT,
            textColor=MUTED,
        ),
        cover_title=ParagraphStyle(
            "cover_title",
            parent=sans,
            fontName=SANS_SEMIBOLD,
            fontSize=34,
            leading=40,
            spaceAfter=10,
        ),
        cover_sub=ParagraphStyle(
            "cover_sub",
            parent=sans,
            fontName=SANS_MEDIUM,
            fontSize=16,
            leading=22,
            textColor=ACCENT_DARK,
            spaceAfter=28,
        ),
        cover_meta=ParagraphStyle(
            "cover_meta", parent=sans, fontSize=10.5, leading=16, textColor=TEXT
        ),
        table_head=ParagraphStyle(
            "table_head",
            parent=sans,
            fontName=SANS_SEMIBOLD,
            fontSize=9,
            leading=12,
            textColor=MUTED,
        ),
        table_cell=ParagraphStyle("table_cell", parent=sans, fontSize=9.5, leading=13),
        bullet=bullets,
    )


# --- Textos -------------------------------------------------------------------------

LABELS: dict[str, dict[str, str]] = {
    "es": {
        "summary": "Resumen para estudiar",
        "outline": "Esquema de examen",
        "contents": "Índice",
        "map": "Mapa del libro",
        "connections": "Cómo se conectan los temas",
        "book": "Libro",
        "date": "Fecha",
        "level": "Nivel de detalle",
        "exam_type": "Tipo de examen",
        "generated": "Generado con Criba",
        "pages": "Páginas del libro",
        "priority": "Prioridad",
        "priority.alta": "Alta",
        "priority.media": "Media",
        "priority.baja": "Baja",
        "imp.3": "Imprescindible",
        "imp.2": "Importante",
        "imp.1": "Complementario",
        "skip": "Lo que puedes saltarte",
        "key_ideas": "Ideas clave",
        "chapter_summary": "De qué va",
        "fell": "Ha caído en examen",
        "not_processed": "Páginas no procesadas",
        "not_processed_text": "No se han podido procesar estas páginas del libro: {pages}. "
        "Revísalas directamente en el libro.",
        "study_priorities": "Prioridades de estudio",
        "study_priorities_text": "Capítulos de más a menos importante. Las horas indican cómo "
        "repartir cada 10 horas de estudio según la prioridad y la extensión.",
        "chapter": "Capítulo",
        "hours": "Horas",
        "scheme": "Esquema",
        "questions": "Preguntas probables",
        "answer": "Guion de respuesta",
        "why": "Por qué puede caer",
        "deduction": "Las preguntas probables son una deducción a partir del texto, "
        "no información del libro.",
        "see_solutions": "Solución al final",
        "checklist": "Checklist de repaso",
        "checklist_text": "Todos los conceptos imprescindibles (★★★). Márcalos a mano "
        "cuando los domines.",
        "solutions": "Soluciones de las preguntas tipo test",
        "q.test": "Test",
        "q.corta": "Corta",
        "q.desarrollo": "Desarrollo",
        "q.problema": "Problema",
        "level.esencial": "Esencial (≈10 % del libro)",
        "level.normal": "Normal (≈15 % del libro)",
        "level.completo": "Completo (≈20 % del libro)",
        "exam.test": "Test",
        "exam.desarrollo": "Desarrollo",
        "exam.mixto": "Mixto",
        "page_of": "Página",
        "pdf_page": "Pág.",
        "no_chapters": "No hay capítulos procesados.",
    },
    "en": {
        "summary": "Study summary",
        "outline": "Exam outline",
        "contents": "Contents",
        "map": "Book map",
        "connections": "How the topics connect",
        "book": "Book",
        "date": "Date",
        "level": "Level of detail",
        "exam_type": "Exam type",
        "generated": "Made with Criba",
        "pages": "Book pages",
        "priority": "Priority",
        "priority.alta": "High",
        "priority.media": "Medium",
        "priority.baja": "Low",
        "imp.3": "Essential",
        "imp.2": "Important",
        "imp.1": "Supplementary",
        "skip": "What you can skip",
        "key_ideas": "Key ideas",
        "chapter_summary": "What it is about",
        "fell": "Came up in past exams",
        "not_processed": "Pages not processed",
        "not_processed_text": "These pages of the book could not be processed: {pages}. "
        "Check them in the book.",
        "study_priorities": "Study priorities",
        "study_priorities_text": "Chapters from most to least important. Hours show how to "
        "split every 10 hours of study by priority and length.",
        "chapter": "Chapter",
        "hours": "Hours",
        "scheme": "Outline",
        "questions": "Likely questions",
        "answer": "Answer outline",
        "why": "Why it may come up",
        "deduction": "Likely questions are inferred from the text, not stated in the book.",
        "see_solutions": "Answer at the end",
        "checklist": "Review checklist",
        "checklist_text": "Every essential concept (★★★). Tick them off by hand once "
        "you know them.",
        "solutions": "Multiple-choice answers",
        "q.test": "Multiple choice",
        "q.corta": "Short",
        "q.desarrollo": "Essay",
        "q.problema": "Problem",
        "level.esencial": "Essential (≈10% of the book)",
        "level.normal": "Normal (≈15% of the book)",
        "level.completo": "Complete (≈20% of the book)",
        "exam.test": "Multiple choice",
        "exam.desarrollo": "Essay",
        "exam.mixto": "Mixed",
        "page_of": "Page",
        "pdf_page": "Page",
        "no_chapters": "No chapters were processed.",
    },
}
MONTHS = {
    "es": "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre "
    "diciembre".split(),
    "en": "January February March April May June July August September October November "
    "December".split(),
}


def labels(language: str) -> dict[str, str]:
    """Textos de los PDF en el idioma del libro (español si no está disponible)."""
    return LABELS.get(language, LABELS["es"])


def format_date(iso: str, language: str) -> str:
    """«18 de octubre de 2026» / «October 18, 2026»."""
    year, month, day = (int(x) for x in iso[:10].split("-"))
    if language == "en":
        return f"{MONTHS['en'][month - 1]} {day}, {year}"
    return f"{day} de {MONTHS['es'][month - 1]} de {year}"


def esc(text: str) -> str:
    """Escapa el texto para los párrafos de ReportLab (que usan marcado XML)."""
    return escape(text, {'"': "&quot;"})


def page_ref(pages: list[int] | tuple[int, ...]) -> str:
    """Referencia de página: «p. 45», «pp. 45–47», «pp. 12, 15–17»."""
    nums = sorted(set(pages))
    if not nums:
        return ""
    groups: list[list[int]] = []
    for n in nums:
        if groups and n == groups[-1][-1] + 1:
            groups[-1].append(n)
        else:
            groups.append([n])
    parts = [str(g[0]) if len(g) == 1 else f"{g[0]}–{g[-1]}" for g in groups]
    prefix = "p." if len(nums) == 1 else "pp."
    return f"{prefix} {', '.join(parts)}"


def page_span(start: int, end: int) -> str:
    """«2–21» o «5»: rango de páginas sin prefijo (para columnas y cabeceras)."""
    return str(start) if start == end else f"{start}–{end}"


def ref_markup(pages: list[int] | tuple[int, ...]) -> str:
    """Referencia en gris y 9 pt, para añadir al final de un párrafo."""
    ref = page_ref(pages)
    if not ref:
        return ""
    return f' <font name="{SANS}" size="{REF_SIZE}" color="{MUTED.hexval()}">({ref})</font>'


def priority_markup(priority: str, language: str) -> str:
    """Etiqueta de prioridad: color + texto + puntos (se lee también en blanco y negro)."""
    color = PRIORITY_COLORS[priority].hexval()
    text = labels(language)[f"priority.{priority}"].upper()
    return f'<font name="{SANS_SEMIBOLD}" color="{color}">{PRIORITY_DOTS[priority]} {text}</font>'
