"""Lectura de páginas escaneadas con la visión de Claude (etapa 3 del spec §6).

Las páginas se renderizan a 150 ppp y se envían por lotes de 5.
"""

from pathlib import Path

import pymupdf

from criba.core import schemas
from criba.core.analyze import prompt
from criba.core.llm import Content, Image, LLMRequest

DPI = 150
BATCH = 5
JPEG_QUALITY = 80
OCR_MAX_TOKENS = 16_000


def batches(pages: list[int], size: int = BATCH) -> list[list[int]]:
    """Agrupa las páginas en lotes de ``size``."""
    return [pages[i : i + size] for i in range(0, len(pages), size)]


def render_pages(pdf: Path, pages: list[int]) -> list[Image]:
    """Renderiza las páginas (numeradas desde 1) a JPEG."""
    images: list[Image] = []
    with pymupdf.open(pdf) as doc:
        for number in pages:
            pix = doc[number - 1].get_pixmap(dpi=DPI)
            images.append(Image(pix.tobytes("jpeg", jpg_quality=JPEG_QUALITY)))
    return images


def ocr_request(pdf: Path, pages: list[int]) -> LLMRequest:
    """Petición de OCR para un lote de páginas."""
    content: Content = []
    for number, image in zip(pages, render_pages(pdf, pages), strict=True):
        content += [f"Página {number}:", image]
    return LLMRequest(
        system=prompt("ocr").render(),
        content=content,
        schema=schemas.OcrResultado,
        max_tokens=OCR_MAX_TOKENS,
        context={"paginas_ocr": pages},
    )
