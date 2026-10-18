"""Regresiones encontradas en la revisión de código de la F1."""

from pathlib import Path

import pymupdf

from criba.core import ingest, structure
from criba.core.ingest import Line, Page, Paragraph
from tests.test_structure import _book

BODY = "Texto del cuerpo con información evaluable y suficiente longitud para un párrafo. "


def _pdf(path: Path, build) -> Path:
    doc = pymupdf.open()
    build(doc)
    doc.save(path)
    return path


# 1. Dos columnas -------------------------------------------------------------------


def test_two_columns_read_left_then_right(tmp_path) -> None:
    def build(doc):
        for n in range(3):
            page = doc.new_page()
            page.insert_textbox(pymupdf.Rect(50, 150, 290, 300), f"IZQ-A{n} " + BODY, fontsize=10)
            page.insert_textbox(pymupdf.Rect(310, 160, 550, 310), f"DER-A{n} " + BODY, fontsize=10)
            page.insert_textbox(pymupdf.Rect(50, 350, 290, 500), f"IZQ-B{n} " + BODY, fontsize=10)
            page.insert_textbox(pymupdf.Rect(310, 360, 550, 510), f"DER-B{n} " + BODY, fontsize=10)

    book = ingest.open_book(_pdf(tmp_path / "cols.pdf", build))
    order = [p.text.split()[0] for p in book.pages[0].paragraphs]
    assert order == ["IZQ-A0", "IZQ-B0", "DER-A0", "DER-B0"]


def test_full_width_title_stays_before_columns(tmp_path) -> None:
    def build(doc):
        page = doc.new_page()
        page.insert_textbox(pymupdf.Rect(50, 110, 550, 140), "Título a todo el ancho", fontsize=16)
        page.insert_textbox(pymupdf.Rect(50, 150, 290, 300), "IZQ " + BODY, fontsize=10)
        page.insert_textbox(pymupdf.Rect(310, 150, 550, 300), "DER " + BODY, fontsize=10)
        page.insert_textbox(pymupdf.Rect(50, 450, 550, 600), "FINAL " + BODY * 2, fontsize=10)

    book = ingest.open_book(_pdf(tmp_path / "mix.pdf", build))
    order = [p.text.split()[0] for p in book.pages[0].paragraphs]
    assert order == ["Título", "IZQ", "DER", "FINAL"]


# 2. Números de página ---------------------------------------------------------------


def test_edge_content_that_looks_numeric_is_kept(tmp_path) -> None:
    def build(doc):
        for n in range(1, 7):
            page = doc.new_page()
            if n == 3:
                page.insert_text((72, 90), "Civil", fontsize=9)  # palabra, no número romano
                page.insert_text((72, 760), "(3)", fontsize=10)  # nº de ecuación, no el más externo
            page.insert_textbox(pymupdf.Rect(72, 200, 520, 400), BODY * 3 + str(n), fontsize=10)
            page.insert_text((300, 815), str(n), fontsize=8)

    book = ingest.open_book(_pdf(tmp_path / "num.pdf", build))
    text = book.pages[2].text
    assert "Civil" in text
    assert "(3)" in text
    assert not any(p.text.strip() == "3" for p in book.pages[2].paragraphs)


def test_strict_roman_numerals() -> None:
    assert ingest._PAGE_NUMBER.match("xiv")
    assert ingest._PAGE_NUMBER.match("— 12 —")
    assert ingest._PAGE_NUMBER.match("Página 7")
    assert not ingest._PAGE_NUMBER.match("Civil")
    assert not ingest._PAGE_NUMBER.match("mil")
    assert not ingest._PAGE_NUMBER.match("dic")


# 3. Cabeceras que cambian por capítulo ---------------------------------------------


def test_running_header_changing_per_chapter_removed(tmp_path) -> None:
    def build(doc):
        for n in range(40):
            page = doc.new_page()
            page.insert_text(
                (72, 40),
                f"Tema {n // 8 + 1}: Asunto número {['A', 'B', 'C', 'D', 'E'][n // 8]}",
                fontsize=8,
            )
            page.insert_textbox(
                pymupdf.Rect(72, 200, 520, 400), f"Página {n} única. " + BODY * 2, fontsize=10
            )

    book = ingest.open_book(_pdf(tmp_path / "hdr.pdf", build))
    assert not any("Asunto número" in p.text for p in book.pages)


# 4 y 5. Portada repetida y capitulares -------------------------------------------


def test_repeated_cover_title_does_not_become_chapter_level() -> None:
    book = _book([[BODY * 2] for _ in range(30)])
    big = Paragraph([Line("Biología general", 36.0, True)])
    book.pages[0].paragraphs.insert(0, big)
    book.pages[2].paragraphs.insert(0, big)
    for pg, title in [
        (5, "Capítulo 1. Célula"),
        (12, "Capítulo 2. Genes"),
        (20, "Capítulo 3. Evolución"),
    ]:
        book.pages[pg - 1].paragraphs.insert(0, Paragraph([Line(title, 20.0, True)]))
    chapters = structure.detect_chapters(book)
    assert [c.start_page for c in chapters] == [1, 5, 12, 20]


def test_drop_caps_are_not_headings() -> None:
    book = _book([[BODY * 2] for _ in range(20)])
    for pg in (2, 6, 10, 14):
        book.pages[pg].paragraphs.insert(0, Paragraph([Line("E", 40.0, False)]))
    assert structure.detect_chapters(book)[0].source == "blocks"


# 6. Entradas del índice en la misma página -------------------------------------------


def test_toc_entries_on_same_page_are_merged() -> None:
    book = _book([["a"] for _ in range(19)], toc=[(1, "Uno", 5), (1, "Dos", 5), (1, "Tres", 10)])
    chapters = structure.detect_chapters(book)
    assert [(c.title, c.start_page, c.end_page) for c in chapters] == [
        ("Preliminares", 1, 4),
        ("Uno · Dos", 5, 9),
        ("Tres", 10, 19),
    ]


# 7. Párrafos partidos entre páginas y guiones ---------------------------------------


def test_paragraph_continuing_on_next_page_is_joined() -> None:
    book = _book(
        [
            ["Primer párrafo completo.", "La división celular se llama fragmen-"],
            ["tación cuando ocurre así.", "Otro párrafo."],
        ]
    )
    ch = structure.Chapter("C", 1, 2, [], "blocks")
    texts = [p.text for p in structure.chapter_paragraphs(book, ch)]
    assert texts == [
        "Primer párrafo completo.",
        "La división celular se llama fragmentación cuando ocurre así.",
        "Otro párrafo.",
    ]
    assert structure.chapter_paragraphs(book, ch)[1].page == 1


def test_soft_hyphen_and_unicode_hyphen_joined() -> None:
    par = Paragraph([Line("mito­sis y meio‐", 10, False), Line("sis celular", 10, False)])
    assert par.text == "mitosis y meiosis celular"


# 8. Texto sin espacios ---------------------------------------------------------------


def test_text_without_spaces_respects_limit() -> None:
    book = _book([["細胞" * 3000]])
    chunks = structure.chunk_chapter(
        book, structure.Chapter("C", 1, 1, [], "blocks"), max_tokens=1000
    )
    assert chunks and all(c.tokens <= 1000 for c in chunks)
    assert "".join(p.text for c in chunks for p in c.paragraphs) == "細胞" * 3000


# 9. Ganchos para la F2 ---------------------------------------------------------------


def test_ocr_text_can_be_set_and_is_chunked() -> None:
    page = Page(number=1, paragraphs=[], has_images=True)
    assert page.is_scanned
    page.set_ocr_text("Primer párrafo leído por OCR.\n\nSegundo párrafo con la mitosis.")
    assert page.ocr
    assert not page.is_scanned
    assert [p.text for p in page.paragraphs] == [
        "Primer párrafo leído por OCR.",
        "Segundo párrafo con la mitosis.",
    ]


def test_ocr_lines_do_not_affect_font_detection() -> None:
    book = _book([[BODY] for _ in range(10)])
    for p in book.pages:
        p.set_ocr_text("x " * 200)
    assert structure.detect_chapters(book)[0].source == "blocks"


def test_chunker_version_exposed_for_cache_key() -> None:
    assert isinstance(structure.CHUNKER_VERSION, int)
