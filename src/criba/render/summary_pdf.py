"""PDF «Resumen para estudiar» (spec §7, PDF 1)."""

from pathlib import Path

from reportlab.lib.units import mm
from reportlab.platypus import (
    CondPageBreak,
    Flowable,
    PageBreak,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from criba.core.schemas import Capitulo, Concepto, Libro
from criba.render.base import CONTENT_WIDTH, Heading, PageMap, box, build
from criba.render.parts import chapter_key, chapter_meta, cover, unprocessed_note
from criba.render.styles import (
    RULE,
    SANS,
    STARS,
    esc,
    labels,
    page_span,
    priority_markup,
    ref_markup,
    styles,
)

KEY_CONTENTS = "indice"
KEY_MAP = "mapa"


def _contents(libro: Libro, pages: PageMap) -> list[Flowable]:
    st, lb = styles(), labels(libro.idioma)
    rows = [
        [
            Paragraph(lb["chapter"], st.table_head),
            Paragraph(lb["priority"], st.table_head),
            Paragraph(lb["pages"], st.table_head),
            Paragraph(lb["pdf_page"], st.table_head),
        ]
    ]
    for i, cap in enumerate(libro.capitulos):
        key = chapter_key(i)
        rows.append(
            [
                Paragraph(f'<a href="#{key}">{esc(cap.titulo)}</a>', st.toc),
                Paragraph(priority_markup(cap.prioridad, libro.idioma), st.table_cell),
                Paragraph(page_span(*cap.paginas), st.toc_num),
                Paragraph(f'<a href="#{key}">{pages.get(key, "")}</a>', st.toc_num),
            ]
        )
    table = Table(
        rows, colWidths=[CONTENT_WIDTH - 72 * mm, 30 * mm, 28 * mm, 14 * mm], repeatRows=1
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return [
        Heading(lb["contents"], st.h1, key=KEY_CONTENTS, outline=lb["contents"]),
        Spacer(1, 6),
        table,
        PageBreak(),
    ]


def _book_map(libro: Libro) -> list[Flowable]:
    st, lb = styles(), labels(libro.idioma)
    story: list[Flowable] = [Heading(lb["map"], st.h1, key=KEY_MAP, outline=lb["map"])]
    story += unprocessed_note(libro)
    story += [Paragraph(esc(p.strip()), st.lead) for p in libro.mapa.split("\n") if p.strip()]
    if libro.conexiones:
        story.append(Paragraph(lb["connections"], st.h3))
        story += [Paragraph(esc(c), st.bullet[0], bulletText="→") for c in libro.conexiones]
    story.append(PageBreak())
    return story


def _concept(c: Concepto) -> Flowable:
    st = styles()
    title = f"<b>{esc(c.titulo)}.</b>"
    if c.tipo == "definicion":
        parts: list[Flowable] = [
            Paragraph(esc(c.titulo), st.box_title),
            Paragraph(
                esc(c.explicacion) + ("" if c.cita_literal else ref_markup(c.paginas)),
                st.body_tight,
            ),
        ]
        if c.cita_literal:
            parts.append(Paragraph(f"«{esc(c.cita_literal)}»" + ref_markup(c.paginas), st.quote))
        return box(parts)
    if c.tipo == "formula" and c.cita_literal:
        return box(
            [
                Paragraph(esc(c.titulo), st.box_title),
                Paragraph(esc(c.cita_literal), st.formula),
                Paragraph(esc(c.explicacion) + ref_markup(c.paginas), st.body_tight),
            ]
        )
    return Paragraph(f"{title} {esc(c.explicacion)}{ref_markup(c.paginas)}", st.body)


def _chapter(libro: Libro, index: int, cap: Capitulo) -> list[Flowable]:
    st, lb = styles(), labels(libro.idioma)
    key = chapter_key(index)
    story: list[Flowable] = [
        Heading(esc(cap.titulo), st.h1, key=key, outline=cap.titulo),
        chapter_meta(cap, libro.idioma),
        Paragraph(esc(cap.resumen), st.lead),
    ]
    for level in (3, 2, 1):
        concepts = [c for c in cap.conceptos if c.importancia == level]
        if not concepts:
            continue
        sub_key = f"{key}-imp{level}"
        story += [
            CondPageBreak(60),
            Heading(
                f'{lb[f"imp.{level}"]} <font name="{SANS}" size="11">{STARS[level]}</font>',
                st.h2,
                key=sub_key,
                outline=f"{lb[f'imp.{level}']} {STARS[level]}",
                level=1,
            ),
        ]
        for c in concepts:
            story += [_concept(c), Spacer(1, 4)]
    if cap.paja:
        story += [CondPageBreak(60), Paragraph(lb["skip"], st.h3)]
        story += [Paragraph(esc(p), st.small, bulletText="–") for p in cap.paja]
    story.append(PageBreak())
    return story


def story(libro: Libro, pages: PageMap) -> list[Flowable]:
    """Contenido completo del PDF."""
    lb = labels(libro.idioma)
    flow: list[Flowable] = cover(libro, lb["summary"], [])
    flow += _contents(libro, pages)
    flow += _book_map(libro)
    if not libro.capitulos:
        flow.append(Paragraph(lb["no_chapters"], styles().body))
    for i, cap in enumerate(libro.capitulos):
        flow += _chapter(libro, i, cap)
    if isinstance(flow[-1], PageBreak):
        flow.pop()
    return flow


def render(libro: Libro, path: Path) -> Path:
    """Genera el PDF Resumen para estudiar en ``path``."""
    lb = labels(libro.idioma)
    return build(
        path,
        lambda pages: story(libro, pages),
        title=f"{libro.asignatura} – {lb['summary']}",
        footer=f"{libro.asignatura} · {lb['summary']}",
        subject=libro.titulo_libro,
    )
