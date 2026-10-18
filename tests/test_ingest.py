import tracemalloc
from pathlib import Path

import pymupdf
import pytest

from criba.core import ingest
from criba.core.errors import CribaError, ErrorKind


def _make_pdf(
    path: Path,
    pages: list[list[tuple[str, float]]],
    image: bool = False,
    footers: list[str] | None = None,
) -> Path:
    """PDF mínimo: cada página es una lista de (texto, tamaño) en bloques separados.

    El primer bloque cae en la franja de cabecera (y=40); ``footers`` va abajo (y=815).
    """
    doc = pymupdf.open()
    for n, blocks in enumerate(pages):
        page = doc.new_page()
        y = 30.0
        for text, size in blocks:
            page.insert_textbox(pymupdf.Rect(72, y, 520, y + 200), text, fontsize=size)
            y += 90
        if footers:
            page.insert_text((290, 815), footers[n], fontsize=8)
        if image:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 20, 20), False)
            page.insert_image(pymupdf.Rect(100, 600, 200, 700), pixmap=pix)
    doc.save(path)
    return path


# --- Validación (RF-02) ------------------------------------------------------


def test_valid_pdf_info(fx) -> None:
    info = ingest.validate(fx.con_indice)
    assert info.page_count == 25
    assert info.title == "Biología general"
    assert len(info.sha256) == 64
    assert info.has_toc


def test_title_falls_back_to_filename(tmp_path) -> None:
    pdf = _make_pdf(tmp_path / "Historia de España.pdf", [[("Hola", 11)]])
    assert ingest.validate(pdf).title == "Historia de España"


def test_sha256_is_stable_and_content_based(fx, tmp_path) -> None:
    copy = tmp_path / "copia.pdf"
    copy.write_bytes(fx.con_indice.read_bytes())
    assert ingest.validate(copy).sha256 == ingest.validate(fx.con_indice).sha256
    assert ingest.validate(fx.sin_indice).sha256 != ingest.validate(fx.con_indice).sha256


@pytest.mark.parametrize(
    ("name", "kind"),
    [("protegido", ErrorKind.PASSWORD_PROTECTED), ("danado", ErrorKind.CORRUPT)],
)
def test_rejected_fixtures(fx, name: str, kind: ErrorKind) -> None:
    with pytest.raises(CribaError) as exc:
        ingest.validate(getattr(fx, name))
    assert exc.value.kind is kind


def test_missing_file(tmp_path) -> None:
    with pytest.raises(CribaError) as exc:
        ingest.validate(tmp_path / "no.pdf")
    assert exc.value.kind is ErrorKind.NOT_FOUND


def test_non_pdf_file_is_corrupt(tmp_path) -> None:
    txt = tmp_path / "apuntes.pdf"
    txt.write_text("esto no es un pdf", encoding="utf-8")
    with pytest.raises(CribaError) as exc:
        ingest.validate(txt)
    assert exc.value.kind is ErrorKind.CORRUPT


def test_too_many_pages(fx, monkeypatch) -> None:
    monkeypatch.setattr(ingest, "MAX_PAGES", 10)
    with pytest.raises(CribaError) as exc:
        ingest.validate(fx.con_indice)
    assert exc.value.kind is ErrorKind.TOO_MANY_PAGES


def test_too_large(fx, monkeypatch) -> None:
    monkeypatch.setattr(ingest, "MAX_BYTES", 1000)
    with pytest.raises(CribaError) as exc:
        ingest.validate(fx.con_indice)
    assert exc.value.kind is ErrorKind.TOO_LARGE


def test_errors_have_friendly_message_and_action() -> None:
    for kind in ErrorKind:
        err = CribaError(kind)
        assert err.message and not err.message.startswith(("Traceback", "Error:"))
        assert err.actions


def test_error_str_never_contains_details() -> None:
    err = CribaError(ErrorKind.CORRUPT, detail="FileDataError: xref broken at 0x1f")
    assert "xref" not in err.message
    assert "xref" in err.detail


# --- Extracción y limpieza ---------------------------------------------------


def test_extracts_pages_with_paragraphs(fx) -> None:
    book = ingest.open_book(fx.con_indice)
    assert len(book.pages) == 25
    assert [p.number for p in book.pages] == list(range(1, 26))
    body = book.pages[2]
    assert body.paragraphs, "debería haber párrafos"
    assert any("célula" in p.text for page in book.pages for p in page.paragraphs)


def test_keeps_font_size_and_bold(fx) -> None:
    book = ingest.open_book(fx.con_indice)
    lines = [ln for p in book.pages[1].paragraphs for ln in p.lines]
    title = next(ln for ln in lines if ln.text.startswith("Capítulo 1"))
    assert title.size == pytest.approx(20)
    assert title.bold
    body = next(ln for ln in lines if ln.size == pytest.approx(10.5))
    assert not body.bold


def test_removes_repeated_headers_and_page_numbers(fx) -> None:
    book = ingest.open_book(fx.con_indice)
    all_text = "\n".join(p.text for page in book.pages for p in page.paragraphs)
    assert "Edición de prueba" not in all_text
    for page in book.pages:
        for par in page.paragraphs:
            assert par.text.strip() != str(page.number)


def test_header_alternating_odd_even_pages_removed(tmp_path) -> None:
    body = "Texto del cuerpo con contenido suficiente para ser una página normal de libro. " * 3
    pages = []
    for i in range(1, 11):
        header = "Manual de Química" if i % 2 == 0 else f"Tema {i // 4 + 1}: Átomos"
        pages.append([(header, 8), (body + f" Variante {i}.", 11)])
    footers = [f"— {i} —" for i in range(1, 11)]
    book = ingest.open_book(_make_pdf(tmp_path / "alt.pdf", pages, footers=footers))
    text = "\n".join(p.text for page in book.pages for p in page.paragraphs)
    assert "Manual de Química" not in text
    assert "Átomos" not in text  # se repite en impares, normalizando números
    assert "Variante 7" in text
    assert "— 3 —" not in text


def test_repeated_body_line_is_kept_when_not_at_edges(tmp_path) -> None:
    pages = [
        [
            (f"Cabecera distinta {i}.", 9),
            (f"Inicio distinto {i} con texto propio y largo para el cuerpo.", 11),
            ("Recuerda: la célula es la unidad de la vida.", 11),
            (f"Final distinto {i} de la página con más texto propio.", 11),
        ]
        for i in range(6)
    ]
    book = ingest.open_book(_make_pdf(tmp_path / "rep.pdf", pages))
    assert sum("Recuerda" in p.text for pg in book.pages for p in pg.paragraphs) == 6


def test_scanned_pages_detected(fx) -> None:
    book = ingest.open_book(fx.escaneado)
    assert len(book.pages) == 5
    assert all(p.is_scanned for p in book.pages)
    assert book.scanned_pages == [1, 2, 3, 4, 5]


def test_text_pages_not_scanned(fx) -> None:
    book = ingest.open_book(fx.con_indice)
    assert book.scanned_pages == []


def test_short_page_with_image_is_scanned_but_without_image_is_not(tmp_path) -> None:
    with_img = ingest.open_book(_make_pdf(tmp_path / "a.pdf", [[("Fig. 1", 11)]], image=True))
    assert with_img.pages[0].is_scanned
    no_img = _make_pdf(tmp_path / "b.pdf", [[("Fin.", 11)], [("Texto " * 40, 11)]])
    assert not ingest.open_book(no_img).pages[0].is_scanned


def test_book_without_text_or_images_raises_no_text(tmp_path) -> None:
    doc = pymupdf.open()
    for _ in range(3):
        doc.new_page()
    doc.save(tmp_path / "vacio.pdf")
    with pytest.raises(CribaError) as exc:
        ingest.open_book(tmp_path / "vacio.pdf")
    assert exc.value.kind is ErrorKind.NO_TEXT


def test_long_book_streams_pages(fx) -> None:
    book = ingest.open_book(fx.largo)
    assert len(book.pages) == 501
    assert book.info.has_toc


def test_progress_callback(fx) -> None:
    seen: list[tuple[int, int]] = []
    ingest.open_book(fx.con_indice, on_page=lambda done, total: seen.append((done, total)))
    assert seen[-1] == (25, 25)
    assert len(seen) == 25


def test_memory_stays_bounded_on_long_book(fx) -> None:
    """RNF-02: solo se guarda texto; 500 páginas no deben pasar de unas decenas de MB."""
    tracemalloc.start()
    ingest.open_book(fx.largo)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert peak < 150 * 1024 * 1024
