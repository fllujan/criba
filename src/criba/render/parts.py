"""Partes que comparten los dos PDF: portada, cabecera de capítulo y avisos."""

from reportlab.lib.units import cm
from reportlab.platypus import Flowable, NextPageTemplate, PageBreak, Paragraph, Spacer

from criba.core.schemas import Capitulo, Libro
from criba.render.base import box
from criba.render.styles import (
    BOX_BG,
    PRIORITY_COLORS,
    esc,
    format_date,
    labels,
    page_span,
    priority_markup,
    styles,
)


def chapter_key(index: int) -> str:
    """Destino del capítulo para marcadores y enlaces."""
    return f"cap{index}"


def cover(libro: Libro, subtitle: str, extra: list[tuple[str, str]]) -> list[Flowable]:
    """Portada: asignatura, título del libro, fecha, nivel y «Generado con Criba»."""
    st, lb = styles(), labels(libro.idioma)
    rows = [
        (lb["book"], libro.titulo_libro),
        (lb["date"], format_date(libro.fecha, libro.idioma)),
        (lb["level"], lb[f"level.{libro.nivel}"]),
        *extra,
    ]
    meta = "<br/>".join(f"<font color='#7F8C8D'>{esc(k)}:</font> {esc(v)}" for k, v in rows)
    return [
        NextPageTemplate("cover"),
        Spacer(1, 6.5 * cm),
        Paragraph(esc(libro.asignatura), st.cover_title),
        Paragraph(esc(subtitle), st.cover_sub),
        Paragraph(meta, st.cover_meta),
        Spacer(1, 8 * cm),
        Paragraph(lb["generated"], st.small),
        NextPageTemplate("normal"),
        PageBreak(),
    ]


def chapter_meta(cap: Capitulo, language: str) -> Paragraph:
    """«Páginas del libro 2–9 · ●●● ALTA · Ha caído en examen»."""
    st, lb = styles(), labels(language)
    parts = [
        f"{lb['pages']} {page_span(*cap.paginas)}",
        priority_markup(cap.prioridad, language),
    ]
    if cap.ha_caido_en_examen:
        parts.append(fell_markup(language))
    return Paragraph(" · ".join(parts), st.meta)


def fell_markup(language: str) -> str:
    """Etiqueta «Ha caído en examen» (con símbolo, no solo color)."""
    color = PRIORITY_COLORS["alta"].hexval()
    return (
        f'<font name="Inter-SemiBold" color="{color}">◆ {labels(language)["fell"].upper()}</font>'
    )


def unprocessed_note(libro: Libro) -> list[Flowable]:
    """Aviso RNF-05 si hubo páginas que no se pudieron procesar."""
    if not libro.paginas_no_procesadas:
        return []
    st, lb = styles(), labels(libro.idioma)
    pages = ", ".join(str(a) if a == b else f"{a}–{b}" for a, b in libro.paginas_no_procesadas)
    text = esc(lb["not_processed_text"].format(pages=pages))
    return [
        box(
            [Paragraph(lb["not_processed"], st.box_title), Paragraph(text, st.body_tight)],
            background=BOX_BG,
            border=PRIORITY_COLORS["alta"],
        ),
        Spacer(1, 10),
    ]
