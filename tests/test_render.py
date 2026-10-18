"""PDF de salida (spec §7 y §9 «Render»)."""

from pathlib import Path

import pymupdf
import pytest

from criba.core import schemas
from criba.core.errors import CribaError, ErrorKind
from criba.render import output_names, render_book
from criba.render.outline_pdf import bold_keywords, study_hours
from criba.render.styles import format_date, page_ref, page_span


def _concepto(titulo, importancia, paginas, tipo="idea_clave", cita=None):
    return schemas.Concepto(
        titulo=titulo,
        explicacion=f"Explicación de {titulo}.",
        tipo=tipo,
        importancia=importancia,
        paginas=paginas,
        cita_literal=cita,
    )


def _libro(**kw) -> schemas.Libro:
    hoja = schemas.NodoHoja(texto="Fases de la mitosis", negrita=["mitosis"], paginas=[4])
    medio = schemas.NodoMedio(
        texto="División celular", negrita=["División"], paginas=[3, 4], hijos=[hoja]
    )
    test_q = schemas.PreguntaProbable(
        pregunta="¿Cuál es la unidad de la vida?",
        tipo="test",
        respuesta_clave="La célula.",
        opciones=["El átomo", "La célula", "El tejido", "El órgano"],
        correcta=1,
        paginas=[2],
        motivo="Definición formal.",
    )
    dev_q = schemas.PreguntaProbable(
        pregunta="Explica la mitosis.",
        tipo="desarrollo",
        respuesta_clave="Cuatro fases…",
        opciones=None,
        correcta=None,
        paginas=[4, 5],
        motivo="Proceso paso a paso.",
    )
    cap1 = schemas.Capitulo(
        titulo="Capítulo 1. La célula <y> & cía",
        paginas=(2, 9),
        prioridad="alta",
        resumen="La célula es la unidad básica.",
        esquema=[
            schemas.NodoEsquema(
                texto="Teoría celular", negrita=["celular"], paginas=[2], hijos=[medio]
            )
        ],
        conceptos=[
            _concepto("Célula", 3, [2], tipo="definicion", cita="La célula es la unidad."),
            _concepto("Ley de Fick", 3, [5], tipo="formula", cita="J = −D · dC/dx"),
            _concepto("Orgánulos", 2, [6, 7, 8]),
            _concepto("Historia del microscopio", 1, [9]),
        ],
        preguntas=[test_q, dev_q],
        paja=["Anécdota de Hooke (p. 3)"],
        ha_caido_en_examen=True,
    )
    cap2 = cap1.model_copy(
        update={
            "titulo": "Capítulo 2. Genética",
            "paginas": (10, 30),
            "prioridad": "baja",
            "ha_caido_en_examen": False,
            "preguntas": [test_q],
        }
    )
    base = {
        "asignatura": "Biología: 1.º",
        "titulo_libro": "Biología general",
        "archivo": "libro.pdf",
        "sha256": "0" * 64,
        "paginas_libro": 30,
        "nivel": "normal",
        "tipo_examen": "mixto",
        "idioma": "es",
        "modelo": "claude-sonnet-5-5",
        "fecha": "2026-10-18T08:00:00+00:00",
        "mapa": "El libro va de biología.\n\nEmpieza por la célula.",
        "conexiones": ["Célula → Genética: base"],
        "capitulos": [cap1, cap2],
        "paginas_no_procesadas": [(20, 22)],
        "paginas_ocr": [],
        "coste_usd": 0.5,
    }
    return schemas.Libro.model_validate(base | kw)


@pytest.fixture
def pdfs(tmp_path: Path):
    return render_book(_libro(), tmp_path)


def _text(path: Path) -> str:
    return "\n".join(page.get_text() for page in pymupdf.open(path))


def test_file_names_follow_spec(pdfs) -> None:
    summary, outline = pdfs
    assert summary.name == "Biología 1.º - Resumen.pdf"
    assert outline.name == "Biología 1.º - Esquema de examen.pdf"
    assert output_names("Física") == ("Física - Resumen.pdf", "Física - Esquema de examen.pdf")


def test_pdfs_open_are_a4_and_have_metadata(pdfs) -> None:
    for path in pdfs:
        doc = pymupdf.open(path)
        assert doc.page_count > 3
        w, h = doc[0].rect.width, doc[0].rect.height
        assert (round(w), round(h)) == (595, 842)
        assert doc.metadata["author"] == "Criba"
        assert not list(path.parent.glob(".*.tmp"))


def test_summary_bookmarks_and_titles(pdfs) -> None:
    summary, _ = pdfs
    toc = pymupdf.open(summary).get_toc()
    titles = [t for _, t, _ in toc]
    assert titles[:3] == ["Índice", "Mapa del libro", "Capítulo 1. La célula <y> & cía"]
    assert "Imprescindible ★★★" in titles
    assert [lvl for lvl, t, _ in toc if t.startswith("Capítulo")] == [1, 1]
    text = _text(summary)
    for expected in (
        "Resumen para estudiar",
        "Generado con Criba",
        "18 de octubre de 2026",
        "Normal (≈15 % del libro)",
        "Lo que puedes saltarte",
        "Anécdota de Hooke",
        "J = −D · dC/dx",
        "«La célula es la unidad.»",
        "Cómo se conectan los temas",
    ):
        assert expected in text, expected


def test_outline_bookmarks_and_sections(pdfs) -> None:
    _, outline = pdfs
    titles = [t for _, t, _ in pymupdf.open(outline).get_toc()]
    assert titles[0] == "Prioridades de estudio"
    assert "Checklist de repaso" in titles
    assert titles[-1] == "Soluciones de las preguntas tipo test"
    text = _text(outline)
    for expected in (
        "Esquema de examen",
        "Tipo de examen",
        "Mixto",
        "Preguntas probables",
        "Guion de respuesta",
        "Por qué puede caer",
        "Solución al final",
        "Fases de la mitosis",
    ):
        assert expected in text, expected


def test_toc_links_point_to_chapter_pages(pdfs) -> None:
    summary, _ = pdfs
    doc = pymupdf.open(summary)
    toc_pages = {t: p for _, t, p in doc.get_toc()}
    links = [
        lk
        for lk in doc[1].get_links()
        if lk.get("kind") == pymupdf.LINK_GOTO or lk.get("kind") == pymupdf.LINK_NAMED
    ]
    assert len(links) >= 4  # título y número de página de cada capítulo
    targets = {lk.get("page") for lk in links if lk.get("page") is not None}
    assert toc_pages["Capítulo 1. La célula <y> & cía"] - 1 in targets


def test_toc_shows_pdf_page_numbers(pdfs) -> None:
    summary, _ = pdfs
    doc = pymupdf.open(summary)
    chapter_page = {t: p for _, t, p in doc.get_toc()}["Capítulo 2. Genética"]
    assert str(chapter_page) in doc[1].get_text()


def test_every_item_has_gray_page_reference(pdfs) -> None:
    summary, outline = pdfs
    s = _text(summary)
    assert "(p. 2)" in s and "(pp. 6–8)" in s
    o = _text(outline)
    assert "(pp. 4, 5)" in o or "(pp. 4–5)" in o


def test_priority_readable_in_black_and_white(pdfs) -> None:
    """La prioridad nunca va solo en color: texto + puntos."""
    summary, outline = pdfs
    for path in (summary, outline):
        text = _text(path)
        assert "●●● ALTA" in text and "●○○ BAJA" in text
    assert "★★★" in _text(summary)


def test_fell_in_exam_label_and_unprocessed_note(pdfs) -> None:
    for path in pdfs:
        text = _text(path)
        assert "HA CAÍDO EN EXAMEN" in text
        assert "Páginas no procesadas" in text and "20–22" in text


def test_checklist_has_all_essentials(pdfs) -> None:
    _, outline = pdfs
    doc = pymupdf.open(outline)
    page = {t: p for _, t, p in doc.get_toc()}["Checklist de repaso"]
    text = doc[page - 1].get_text()
    assert text.count("Célula") >= 2 and "Ley de Fick" in text
    assert "Orgánulos" not in text  # solo los ★★★


def test_solutions_numbered_across_chapters(pdfs) -> None:
    _, outline = pdfs
    doc = pymupdf.open(outline)
    text = doc[doc.page_count - 1].get_text()
    assert "1. b)" in text and "3. b)" in text  # preguntas 1 y 3 son tipo test
    assert "La célula" in text


def test_fonts_embedded(pdfs) -> None:
    for path in pdfs:
        doc = pymupdf.open(path)
        fonts = {f[3] for page in doc for f in page.get_fonts()}
        assert any("Inter" in f for f in fonts) and any("SourceSerif4" in f for f in fonts)


def test_english_labels(tmp_path) -> None:
    summary, outline = render_book(_libro(idioma="en"), tmp_path)
    assert "Study summary" in _text(summary) and "October 18, 2026" in _text(summary)
    assert "Likely questions" in _text(outline)


def test_unknown_language_falls_back_to_spanish(tmp_path) -> None:
    summary, _ = render_book(_libro(idioma="de"), tmp_path)
    assert "Resumen para estudiar" in _text(summary)


def test_no_chapters_and_no_test_questions(tmp_path) -> None:
    summary, outline = render_book(
        _libro(capitulos=[], conexiones=[], paginas_no_procesadas=[]), tmp_path
    )
    assert "No hay capítulos procesados" in _text(summary)
    assert "Soluciones" not in _text(outline)


def test_long_content_spans_pages(tmp_path) -> None:
    libro = _libro()
    big = libro.capitulos[0].model_copy(
        update={
            "conceptos": [_concepto(f"Concepto {i}", 1 + i % 3, [2 + i % 8]) for i in range(150)],
        }
    )
    summary, _ = render_book(libro.model_copy(update={"capitulos": [big]}), tmp_path)
    assert pymupdf.open(summary).page_count > 6


def test_cannot_write_raises_friendly_error(tmp_path) -> None:
    blocker = tmp_path / "f"
    blocker.write_text("no soy carpeta")
    with pytest.raises(CribaError) as exc:
        render_book(_libro(), blocker)
    assert exc.value.kind in {ErrorKind.CANNOT_WRITE, ErrorKind.DISK_FULL}


def test_helpers() -> None:
    assert page_ref([45]) == "p. 45"
    assert page_ref([47, 45, 46]) == "pp. 45–47"
    assert page_ref([12, 15, 16, 17]) == "pp. 12, 15–17"
    assert page_ref([]) == ""
    assert page_span(5, 5) == "5" and page_span(2, 9) == "2–9"
    assert format_date("2026-01-05T00:00:00", "es") == "5 de enero de 2026"
    assert bold_keywords("La mitosis & la Meiosis", ["meiosis", "mitosis"]) == (
        "La <b>mitosis</b> &amp; la <b>Meiosis</b>"
    )
    assert bold_keywords("<x>", []) == "&lt;x&gt;"


def test_study_hours_sum_to_ten_and_follow_priority() -> None:
    caps = _libro().capitulos
    hours = study_hours(caps)
    assert sum(hours) == pytest.approx(10, abs=0.11)
    # Capítulo 1: alta y 8 págs (3×8=24); capítulo 2: baja y 21 págs (1×21=21).
    assert hours[0] > hours[1]
