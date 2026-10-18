import pymupdf
import pytest

from criba.render.thumbnail import first_page_png


def test_first_page_png_has_requested_width(fx) -> None:
    png = first_page_png(fx.con_indice, width=240)
    assert png.startswith(b"\x89PNG")
    pix = pymupdf.Pixmap(png)
    assert pix.width == 240
    assert pix.height > pix.width  # A4 vertical


def test_first_page_png_unreadable_file_raises(tmp_path) -> None:
    bad = tmp_path / "x.pdf"
    bad.write_bytes(b"no es un pdf")
    with pytest.raises(OSError):
        first_page_png(bad)
