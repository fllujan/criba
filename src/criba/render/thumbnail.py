"""Miniatura de la primera página de un PDF (pantalla Listo)."""

from pathlib import Path

import pymupdf


def first_page_png(pdf: Path, width: int = 360) -> bytes:
    """PNG de la primera página con ``width`` píxeles de ancho. Lanza ``OSError`` si no abre."""
    try:
        with pymupdf.open(pdf) as doc:
            page = doc[0]
            zoom = width / page.rect.width
            pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
            return bytes(pix.tobytes("png"))
    except (RuntimeError, ValueError, IndexError) as exc:  # FileDataError hereda de RuntimeError
        raise OSError(f"no se puede abrir {pdf.name}") from exc
