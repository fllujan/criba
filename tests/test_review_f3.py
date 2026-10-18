"""Regresiones encontradas en la revisión de código de la F3."""

import json
from pathlib import Path

import pymupdf
import pytest

from criba import cli
from criba.core.errors import CribaError, ErrorKind
from criba.render import base, render_book
from criba.render.outline_pdf import bold_keywords
from tests.test_render import _concepto, _libro


def _text(path: Path) -> str:
    return "\n".join(p.get_text() for p in pymupdf.open(path))


def _with_chapter(**update):
    libro = _libro()
    cap = libro.capitulos[0].model_copy(update=update)
    return libro.model_copy(update={"capitulos": [cap]})


def test_very_long_definition_splits_across_pages(tmp_path) -> None:
    long = " ".join(["palabra"] * 1500)
    c = _concepto("Larga", 3, [2], tipo="definicion", cita="Cita.")
    c = c.model_copy(update={"explicacion": long})
    summary, _ = render_book(_with_chapter(conceptos=[c]), tmp_path)
    assert pymupdf.open(summary).page_count > 4


def test_very_long_titles_and_urls(tmp_path) -> None:
    url = "https://ejemplo.org/" + "a" * 3000
    c = _concepto(" ".join(["Título"] * 400), 3, [2])
    libro = _with_chapter(titulo="Capítulo " + " ".join(["largo"] * 600) + url, conceptos=[c])
    summary, outline = render_book(libro, tmp_path)
    assert pymupdf.open(summary).page_count and pymupdf.open(outline).page_count


def test_unexpected_render_error_is_friendly(tmp_path, monkeypatch) -> None:
    def boom(*_a, **_k):
        raise RuntimeError("fallo interno de ReportLab")

    monkeypatch.setattr(base.CribaDoc, "build", boom)
    with pytest.raises(CribaError) as exc:
        render_book(_libro(), tmp_path)
    assert exc.value.kind is ErrorKind.RENDER_FAILED
    assert not list(tmp_path.iterdir())  # ni temporales ni PDF a medias


def test_failed_save_leaves_no_temp_and_keeps_old_pair(tmp_path, monkeypatch) -> None:
    render_book(_libro(), tmp_path)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}

    def locked(self, target):  # en Windows, el PDF abierto en el visor
        raise PermissionError("en uso")

    monkeypatch.setattr(Path, "replace", locked)
    with pytest.raises(CribaError):
        render_book(_libro(asignatura="Biología: 1.º", mapa="Nuevo"), tmp_path)
    monkeypatch.undo()
    after = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert after == before


def test_stars_in_body_text_use_a_font_that_has_them(tmp_path) -> None:
    _, outline = render_book(_libro(), tmp_path)
    doc = pymupdf.open(outline)
    page = {t: p for _, t, p in doc.get_toc()}["Checklist de repaso"]
    spans = [
        s
        for b in doc[page - 1].get_text("dict")["blocks"]
        for line in b.get("lines", [])
        for s in line["spans"]
        if "★" in s["text"]
    ]
    assert spans and all("Inter" in s["font"] for s in spans)


def test_bold_keywords_never_breaks_entities() -> None:
    assert bold_keywords("Tom & Jerry", ["a", "amp"]) == "Tom &amp; Jerry"
    assert bold_keywords("<b>a</b>", ["b"]) == "&lt;<b>b</b>&gt;a&lt;/<b>b</b>&gt;"
    assert bold_keywords("Mitosis y mitosis", ["MITOSIS"]) == "<b>Mitosis</b> y <b>mitosis</b>"


def test_formula_without_quote_still_boxed(tmp_path) -> None:
    c = _concepto("Fórmula sin cita", 3, [2], tipo="formula")
    summary, _ = render_book(_with_chapter(conceptos=[c]), tmp_path)
    assert "Fórmula sin cita" in _text(summary)


def test_long_subject_footer_is_truncated(tmp_path) -> None:
    summary, _ = render_book(_libro(asignatura="Asignatura " * 30), tmp_path)
    page = pymupdf.open(summary)[2]
    footer = [b for b in page.get_text("blocks") if b[1] > page.rect.height - 60]
    assert footer and all(b[2] <= page.rect.width - 40 for b in footer)


def test_cli_bad_json_date_is_friendly(tmp_path, capsys, app_dirs) -> None:
    data = _libro().model_dump(mode="json") | {"fecha": "ayer"}
    path = tmp_path / "datos.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert cli.main([str(path)]) == 2
    assert "Traceback" not in capsys.readouterr().err
