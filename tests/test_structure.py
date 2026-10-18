from itertools import pairwise
from pathlib import Path

import pymupdf
import pytest

from criba.core import ingest, structure
from criba.core.cost import estimate_tokens
from criba.core.ingest import Book, Line, Page, Paragraph, PdfInfo


def _book(pages: list[list[str]], toc: list[tuple[int, str, int]] | None = None) -> Book:
    info = PdfInfo(
        path=Path("x.pdf"),
        sha256="0" * 64,
        page_count=len(pages),
        title="X",
        size_bytes=1,
        has_toc=bool(toc),
    )
    return Book(
        info=info,
        pages=[
            Page(
                number=i + 1,
                paragraphs=[Paragraph([Line(t, 11.0, False)]) for t in texts],
                has_images=False,
            )
            for i, texts in enumerate(pages)
        ],
        toc=list(toc or []),
    )


# --- Capítulos (RF-04) --------------------------------------------------------


def test_chapters_from_toc(fx) -> None:
    book = ingest.open_book(fx.con_indice)
    chapters = structure.detect_chapters(book)
    titles = [c.title for c in chapters]
    assert titles == [
        "Preliminares",
        "Capítulo 1. La célula",
        "Capítulo 2. Genética",
        "Capítulo 3. Evolución",
    ]
    assert all(c.source == "toc" for c in chapters)
    # Cubren el libro entero sin huecos ni solapes.
    assert chapters[0].start_page == 1
    assert chapters[-1].end_page == 25
    for a, b in pairwise(chapters):
        assert b.start_page == a.end_page + 1
    assert chapters[1].sections and chapters[1].sections[0].title == "1.1. Teoría celular"


def test_chapters_from_font_size_without_toc(fx) -> None:
    book = ingest.open_book(fx.sin_indice)
    chapters = structure.detect_chapters(book)
    real = [c for c in chapters if c.title != "Preliminares"]
    assert [c.title for c in real] == [
        "Capítulo 1. La célula",
        "Capítulo 2. Genética",
        "Capítulo 3. Evolución",
    ]
    assert all(c.source == "fonts" for c in real)
    assert real[0].sections, "los apartados (14 pt) deberían detectarse"
    assert chapters[-1].end_page == 25


def test_toc_and_fonts_agree_on_page_ranges(fx) -> None:
    by_toc = structure.detect_chapters(ingest.open_book(fx.con_indice))
    by_font = structure.detect_chapters(ingest.open_book(fx.sin_indice))
    assert [(c.start_page, c.end_page) for c in by_toc] == [
        (c.start_page, c.end_page) for c in by_font
    ]


def test_chapters_fall_back_to_page_blocks() -> None:
    book = _book([["Texto normal de una página sin títulos."] for _ in range(45)])
    chapters = structure.detect_chapters(book)
    assert [(c.start_page, c.end_page) for c in chapters] == [(1, 20), (21, 40), (41, 45)]
    assert chapters[0].title == "Páginas 1–20"
    assert all(c.source == "blocks" for c in chapters)


def test_single_big_title_is_not_enough_for_font_detection() -> None:
    book = _book([["x"] for _ in range(25)])
    book.pages[0].paragraphs = [Paragraph([Line("Gran portada", 30.0, True)])]
    assert structure.detect_chapters(book)[0].source == "blocks"


def test_toc_entries_without_page_are_ignored_and_unordered_sorted() -> None:
    book = _book(
        [["a"] for _ in range(10)],
        toc=[(1, "B", 6), (1, "Roto", -1), (1, "A", 1)],
    )
    chapters = structure.detect_chapters(book)
    assert [(c.title, c.start_page, c.end_page) for c in chapters] == [("A", 1, 5), ("B", 6, 10)]


def test_toc_uses_first_level_with_several_entries() -> None:
    book = _book(
        [["a"] for _ in range(10)],
        toc=[(1, "Libro entero", 1), (2, "Tema 1", 1), (2, "Tema 2", 4), (2, "Tema 3", 8)],
    )
    assert [c.title for c in structure.detect_chapters(book)] == ["Tema 1", "Tema 2", "Tema 3"]


def test_chapter_text_includes_page_markers(fx) -> None:
    book = ingest.open_book(fx.con_indice)
    ch = structure.detect_chapters(book)[1]
    paras = structure.chapter_paragraphs(book, ch)
    assert paras[0].page == ch.start_page
    assert {p.page for p in paras} <= set(range(ch.start_page, ch.end_page + 1))


# --- Fragmentación ------------------------------------------------------------


def _long_chapter_book(n_pages: int = 60) -> Book:
    texts = [
        [
            f"Párrafo {p}-{i}. " + "La fotosíntesis transforma la energía luminosa. " * 12
            for i in range(5)
        ]
        for p in range(n_pages)
    ]
    return _book(texts)


def test_no_chunk_exceeds_limit_and_paragraphs_intact() -> None:
    book = _long_chapter_book()
    ch = structure.Chapter("Todo", 1, len(book.pages), [], "blocks")
    chunks = structure.chunk_chapter(book, ch, max_tokens=2000, overlap_tokens=300)
    assert len(chunks) > 3
    originals = {p.text for pg in book.pages for p in pg.paragraphs}
    for c in chunks:
        assert c.tokens <= 2000
        assert estimate_tokens(c.text) == c.tokens
        for para in c.paragraphs:
            assert para.text in originals  # nunca cortado a mitad


def test_chunks_cover_all_paragraphs_in_order() -> None:
    book = _long_chapter_book()
    ch = structure.Chapter("Todo", 1, len(book.pages), [], "blocks")
    chunks = structure.chunk_chapter(book, ch, max_tokens=2000, overlap_tokens=300)
    got = [p.text for c in chunks for p in c.paragraphs]
    expected = [p.text for pg in book.pages for p in pg.paragraphs]
    assert got == expected


def test_overlap_is_previous_tail_up_to_limit() -> None:
    book = _long_chapter_book()
    ch = structure.Chapter("Todo", 1, len(book.pages), [], "blocks")
    chunks = structure.chunk_chapter(book, ch, max_tokens=2000, overlap_tokens=300)
    assert chunks[0].overlap == ""
    for prev, cur in pairwise(chunks):
        assert cur.overlap
        assert estimate_tokens(cur.overlap) <= 300
        assert prev.paragraphs[-1].text.endswith(cur.overlap.split("…", 1)[-1].strip()[-30:])


def test_chunk_pages_and_ids() -> None:
    book = _long_chapter_book(10)
    ch = structure.Chapter("Todo", 1, 10, [], "blocks")
    chunks = structure.chunk_chapter(book, ch, max_tokens=2000)
    assert chunks[0].start_page == 1 and chunks[-1].end_page == 10
    assert len({c.id for c in chunks}) == len(chunks)
    again = structure.chunk_chapter(book, ch, max_tokens=2000)
    assert [c.id for c in chunks] == [c.id for c in again]  # estables (claves de caché)


def test_text_marks_pages_for_citations() -> None:
    book = _book([["Primera."], ["Segunda."]])
    ch = structure.Chapter("C", 1, 2, [], "blocks")
    (chunk,) = structure.chunk_chapter(book, ch)
    assert chunk.text == "[p. 1]\nPrimera.\n\n[p. 2]\nSegunda."


def test_giant_paragraph_split_by_sentences() -> None:
    giant = " ".join(f"Frase número {i} sobre la mitosis celular." for i in range(800))
    book = _book([[giant]])
    ch = structure.Chapter("C", 1, 1, [], "blocks")
    chunks = structure.chunk_chapter(book, ch, max_tokens=1000)
    assert len(chunks) > 1
    assert all(c.tokens <= 1000 for c in chunks)
    joined = " ".join(p.text for c in chunks for p in c.paragraphs)
    assert joined == giant


def test_default_limits_match_spec() -> None:
    assert structure.MAX_CHUNK_TOKENS == 12_000
    assert structure.OVERLAP_TOKENS == 300
    assert structure.BLOCK_PAGES == 20
    assert pytest.approx(1.3) == structure.HEADING_RATIO


def test_long_fixture_chunks_within_limits(fx) -> None:
    book = ingest.open_book(fx.largo)
    chapters = structure.detect_chapters(book)
    assert len([c for c in chapters if c.source == "toc"]) == 26  # 25 + preliminares
    for ch in chapters:
        for c in structure.chunk_chapter(book, ch):
            assert c.tokens <= structure.MAX_CHUNK_TOKENS


def test_empty_chapter_has_no_chunks() -> None:
    book = _book([[], []])
    assert structure.chunk_chapter(book, structure.Chapter("V", 1, 2, [], "blocks")) == []


def test_pymupdf_toc_roundtrip(tmp_path) -> None:
    doc = pymupdf.open()
    for i in range(4):
        doc.new_page().insert_text((72, 300), f"Contenido propio de la página {i} con texto. " * 2)
    doc.set_toc([[1, "Uno", 1], [1, "Dos", 3]])
    doc.save(tmp_path / "t.pdf")
    chapters = structure.detect_chapters(ingest.open_book(tmp_path / "t.pdf"))
    assert [(c.title, c.start_page, c.end_page) for c in chapters] == [("Uno", 1, 2), ("Dos", 3, 4)]


def test_sentence_without_punctuation_split_by_words() -> None:
    words = " ".join(f"palabra{i}" for i in range(6000))
    book = _book([[words]])
    ch = structure.Chapter("C", 1, 1, [], "blocks")
    chunks = structure.chunk_chapter(book, ch, max_tokens=1000)
    assert all(c.tokens <= 1000 for c in chunks)
    assert " ".join(p.text for c in chunks for p in c.paragraphs) == words
    assert all(len(c.overlap) > 0 and estimate_tokens(c.overlap) <= 300 for c in chunks[1:])
