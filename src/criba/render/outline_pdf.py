"""PDF «Esquema de examen» (spec §7, PDF 2)."""

import re
from dataclasses import dataclass
from pathlib import Path

from reportlab.lib.units import mm
from reportlab.platypus import (
    CondPageBreak,
    Flowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from criba.core.schemas import Capitulo, Libro, NodoHoja, PreguntaProbable
from criba.render.base import CONTENT_WIDTH, CheckBox, Heading, PageMap, build
from criba.render.parts import chapter_key, chapter_meta, cover, unprocessed_note
from criba.render.styles import (
    RULE,
    esc,
    labels,
    page_span,
    priority_markup,
    ref_markup,
    short,
    styles,
)

PRIORITY_WEIGHT = {"alta": 3, "media": 2, "baja": 1}
PRIORITY_ORDER = {"alta": 0, "media": 1, "baja": 2}
LETTERS = "abcd"
KEY_PRIORITIES = "prioridades"
KEY_CHECKLIST = "checklist"
KEY_SOLUTIONS = "soluciones"


@dataclass(frozen=True, slots=True)
class Solution:
    """Solución de una pregunta tipo test."""

    number: int
    question: PreguntaProbable


def study_hours(capitulos: list[Capitulo], total: float = 10) -> list[float]:
    """Horas relativas por capítulo: prioridad × extensión, repartiendo ``total`` horas."""
    weights = [PRIORITY_WEIGHT[c.prioridad] * (c.paginas[1] - c.paginas[0] + 1) for c in capitulos]
    s = sum(weights) or 1
    return [round(total * w / s, 1) for w in weights]


def bold_keywords(text: str, keywords: list[str]) -> str:
    """Pone en negrita las palabras clave de ``text``, escapando cada trozo por separado."""
    words = sorted({k.strip() for k in keywords if k.strip()}, key=len, reverse=True)
    if not words:
        return esc(text)
    pattern = re.compile("|".join(re.escape(w) for w in words), re.IGNORECASE)
    out: list[str] = []
    last = 0
    for m in pattern.finditer(text):
        out += [esc(text[last : m.start()]), f"<b>{esc(m.group(0))}</b>"]
        last = m.end()
    out.append(esc(text[last:]))
    return "".join(out)


def _priorities(libro: Libro, pages: PageMap) -> list[Flowable]:
    st, lb = styles(), labels(libro.idioma)
    order = sorted(
        range(len(libro.capitulos)),
        key=lambda i: (PRIORITY_ORDER[libro.capitulos[i].prioridad], libro.capitulos[i].paginas),
    )
    hours = study_hours(libro.capitulos)
    decimal = "." if libro.idioma == "en" else ","
    rows = [
        [
            Paragraph(h, st.table_head)
            for h in (lb["chapter"], lb["priority"], lb["pages"], lb["hours"], lb["pdf_page"])
        ]
    ]
    for i in order:
        cap = libro.capitulos[i]
        key = chapter_key(i)
        rows.append(
            [
                Paragraph(f'<a href="#{key}">{esc(short(cap.titulo))}</a>', st.table_cell),
                Paragraph(priority_markup(cap.prioridad, libro.idioma), st.table_cell),
                Paragraph(page_span(*cap.paginas), st.table_cell),
                Paragraph(f"{hours[i]:.1f}".replace(".", decimal), st.table_cell),
                Paragraph(f'<a href="#{key}">{pages.get(key, "")}</a>', st.toc_num),
            ]
        )
    table = Table(
        rows, colWidths=[CONTENT_WIDTH - 88 * mm, 30 * mm, 26 * mm, 18 * mm, 14 * mm], repeatRows=1
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
        Heading(lb["study_priorities"], st.h1, key=KEY_PRIORITIES, outline=lb["study_priorities"]),
        Paragraph(esc(lb["study_priorities_text"]), st.body),
        *unprocessed_note(libro),
        table,
        PageBreak(),
    ]


def _node(node: NodoHoja, level: int) -> Paragraph:
    st = styles()
    bullets = ("•", "–", "·")
    return Paragraph(
        bold_keywords(node.texto, node.negrita) + ref_markup(node.paginas),
        st.bullet[level],
        bulletText=bullets[level],
    )


def _question(libro: Libro, number: int, q: PreguntaProbable) -> Flowable:
    st, lb = styles(), labels(libro.idioma)
    head = (
        f'<b>{number}.</b> <font name="Inter-SemiBold" size="8.5" color="#4E6B17">'
        f"{lb[f'q.{q.tipo}'].upper()}</font>  {esc(q.pregunta)}{ref_markup(q.paginas)}"
    )
    parts: list[Flowable] = [Paragraph(head, st.body_tight)]
    if q.tipo == "test" and q.opciones:
        parts += [
            Paragraph(esc(opt), st.bullet[1], bulletText=f"{LETTERS[j]})")
            for j, opt in enumerate(q.opciones)
        ]
        parts.append(Paragraph(lb["see_solutions"], st.small))
    else:
        parts.append(Paragraph(f"<b>{lb['answer']}:</b> {esc(q.respuesta_clave)}", st.bullet[1]))
    parts += [Paragraph(f"<i>{lb['why']}:</i> {esc(q.motivo)}", st.small), Spacer(1, 6)]
    return KeepTogether(parts)


def _chapter(
    libro: Libro, index: int, cap: Capitulo, first_number: int
) -> tuple[list[Flowable], list[Solution]]:
    st, lb = styles(), labels(libro.idioma)
    key = chapter_key(index)
    story: list[Flowable] = [
        Heading(esc(short(cap.titulo, 400)), st.h1, key=key, outline=short(cap.titulo, 120)),
        chapter_meta(cap, libro.idioma),
    ]
    if cap.temas_examen:
        topics = "; ".join(esc(t) for t in cap.temas_examen)
        story.append(Paragraph(f"<b>{lb['fell_topics']}:</b> {topics}", st.small))
    story.append(Paragraph(lb["scheme"], st.h3))
    for n1 in cap.esquema:
        story.append(_node(n1, 0))
        for n2 in n1.hijos:
            story.append(_node(n2, 1))
            story += [_node(n3, 2) for n3 in n2.hijos]
    solutions: list[Solution] = []
    if cap.preguntas:
        story += [
            CondPageBreak(80),
            Heading(
                lb["questions"], st.h2, key=f"{key}-preguntas", outline=lb["questions"], level=1
            ),
            Paragraph(esc(lb["deduction"]), st.small),
            Spacer(1, 4),
        ]
        for offset, q in enumerate(cap.preguntas):
            number = first_number + offset
            story.append(_question(libro, number, q))
            if q.tipo == "test":
                solutions.append(Solution(number, q))
    story.append(PageBreak())
    return story, solutions


def _checklist(libro: Libro) -> list[Flowable]:
    st, lb = styles(), labels(libro.idioma)
    story: list[Flowable] = [
        Heading(lb["checklist"], st.h1, key=KEY_CHECKLIST, outline=lb["checklist"]),
        Paragraph(esc(lb["checklist_text"]), st.body),
    ]
    for cap in libro.capitulos:
        essentials = [c for c in cap.conceptos if c.importancia == 3]  # noqa: PLR2004
        if not essentials:
            continue
        rows = [
            [CheckBox(), Paragraph(f"{esc(short(c.titulo))}{ref_markup(c.paginas)}", st.table_cell)]
            for c in essentials
        ]
        table = Table(rows, colWidths=[7 * mm, CONTENT_WIDTH - 7 * mm], splitInRow=1)
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story += [CondPageBreak(50), Paragraph(esc(cap.titulo), st.h3), table]
    story.append(PageBreak())
    return story


def _solutions(libro: Libro, solutions: list[Solution]) -> list[Flowable]:
    st, lb = styles(), labels(libro.idioma)
    story: list[Flowable] = [
        Heading(lb["solutions"], st.h1, key=KEY_SOLUTIONS, outline=lb["solutions"]),
    ]
    for s in solutions:
        q = s.question
        if q.opciones is None or q.correcta is None:
            continue
        story.append(
            Paragraph(
                f"<b>{s.number}. {LETTERS[q.correcta]})</b> {esc(q.opciones[q.correcta])}"
                f"{ref_markup(q.paginas)}",
                st.body_tight,
            )
        )
    return story


def story(libro: Libro, pages: PageMap) -> list[Flowable]:
    """Contenido completo del PDF."""
    lb = labels(libro.idioma)
    flow: list[Flowable] = cover(
        libro, lb["outline"], [(lb["exam_type"], lb[f"exam.{libro.tipo_examen}"])]
    )
    flow += _priorities(libro, pages)
    solutions: list[Solution] = []
    number = 1
    for i, cap in enumerate(libro.capitulos):
        part, sols = _chapter(libro, i, cap, number)
        flow += part
        solutions += sols
        number += len(cap.preguntas)
    flow += _checklist(libro)
    if solutions:
        flow += _solutions(libro, solutions)
    elif isinstance(flow[-1], PageBreak):
        flow.pop()
    return flow


def render(libro: Libro, path: Path) -> Path:
    """Genera el PDF Esquema de examen en ``path``."""
    lb = labels(libro.idioma)
    return build(
        path,
        lambda pages: story(libro, pages),
        title=f"{libro.asignatura} – {lb['outline']}",
        footer=f"{libro.asignatura} · {lb['outline']}",
        subject=libro.titulo_libro,
    )
