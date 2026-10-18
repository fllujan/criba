"""Genera los PDF de prueba del spec §9 con contenido sintético (sin derechos de autor).

Uso manual: ``uv run python tests/fixtures/build.py`` escribe los PDF en esta carpeta.
Los tests los generan en un directorio temporal (ver ``tests/conftest.py``).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pymupdf

A4 = pymupdf.paper_rect("a4")
MARGIN = 72
BODY_SIZE = 10.5
HEADER = "Biología general"

TEMAS = [
    ("La célula", ["Teoría celular", "Membrana plasmática", "Orgánulos"]),
    ("Genética", ["Leyes de Mendel", "ADN y ARN", "Mutaciones"]),
    ("Evolución", ["Selección natural", "Especiación", "Pruebas de la evolución"]),
    ("Ecología", ["Ecosistemas", "Cadenas tróficas", "Ciclos biogeoquímicos"]),
    ("Fisiología", ["Sistema nervioso", "Sistema endocrino", "Homeostasis"]),
]


@dataclass(frozen=True)
class Fixtures:
    con_indice: Path
    sin_indice: Path
    escaneado: Path
    protegido: Path
    danado: Path
    largo: Path


def _paragraph(tema: str, apartado: str, n: int) -> str:
    """Párrafo determinista y realista con tildes, eñes y una definición."""
    variantes = [
        f"Se denomina {apartado.lower()} al conjunto de procesos que estudia la {tema.lower()} "
        f"dentro del organismo. Es importante destacar que este concepto aparece en el examen "
        f"con frecuencia, y que su comprensión exige conocer los niveles de organización.",
        f"Como ejemplo, el pequeño pingüino de la Antártida ilustra cómo la {tema.lower()} "
        f"condiciona la adaptación al frío. Este caso es una anécdota frecuente en los libros, "
        f"pero no añade datos nuevos a lo explicado sobre {apartado.lower()}.",
        f"En 1858, Darwin y Wallace publicaron trabajos que se relacionan con {apartado.lower()}. "
        f"Se distinguen tres fases: iniciación, desarrollo y conclusión; cada una presenta "
        f"características propias que conviene memorizar en orden.",
        f"En resumen, {apartado.lower()} se caracteriza por su regulación precisa y por la "
        f"interacción entre factores internos y externos. El año pasado se confirmó este "
        f"modelo mediante experimentos de laboratorio número {n}.",
    ]
    return variantes[n % len(variantes)]


class _Writer:
    """Escribe páginas tipo libro de texto con cabecera, pie y párrafos."""

    def __init__(self, doc: pymupdf.Document) -> None:
        self.doc = doc
        self.page: pymupdf.Page | None = None
        self.y = 0.0

    def new_page(self) -> pymupdf.Page:
        page = self.doc.new_page(width=A4.width, height=A4.height)
        number = self.doc.page_count
        page.insert_text((MARGIN, 40), f"{HEADER} · Edición de prueba", fontsize=8)
        page.insert_text((A4.width / 2, A4.height - 30), str(number), fontsize=8)
        self.page = page
        self.y = MARGIN
        return page

    def block(self, text: str, size: float, bold: bool = False, gap: float = 8) -> None:
        font = "hebo" if bold else "helv"
        height = 400.0
        for _ in range(2):
            if self.page is None or self.y > A4.height - MARGIN - 40:
                self.new_page()
            assert self.page is not None
            rect = pymupdf.Rect(MARGIN, self.y, A4.width - MARGIN, self.y + height)
            rest = self.page.insert_textbox(rect, text, fontsize=size, fontname=font)
            if rest >= 0:
                used = height - rest
                self.y += used + gap
                return
            # No cabe: página nueva y reintento.
            self.page = None
        raise RuntimeError("párrafo demasiado largo para una página")


def _book(
    path: Path,
    *,
    chapters: int,
    pages_per_chapter: int,
    with_toc: bool,
) -> Path:
    doc = pymupdf.open()
    doc.set_metadata({"title": "Biología general", "author": "Criba (fixture)"})
    w = _Writer(doc)
    toc: list[list[object]] = []
    # Portada sin cabeceras repetidas relevantes.
    cover = doc.new_page(width=A4.width, height=A4.height)
    cover.insert_textbox(
        pymupdf.Rect(MARGIN, 300, A4.width - MARGIN, 400), "Biología general", fontsize=32
    )
    for c in range(chapters):
        tema, apartados = TEMAS[c % len(TEMAS)]
        titulo = f"Capítulo {c + 1}. {tema}"
        w.new_page()
        start = doc.page_count
        toc.append([1, titulo, start])
        w.block(titulo, 20, bold=True, gap=16)
        target_end = start + pages_per_chapter - 1
        n = 0
        a = 0
        while doc.page_count < target_end or a < len(apartados):
            apartado = apartados[a % len(apartados)]
            if a >= len(apartados):
                apartado = f"{apartado}: ampliación {chr(65 + a % 26)}{a // 26 or ''}"
            sub = f"{c + 1}.{a + 1}. {apartado}"
            w.block(sub, 14, bold=True, gap=10)
            if w.page is not None:
                toc.append([2, sub, doc.page_count])
            for _ in range(3):
                w.block(_paragraph(tema, apartado, n), BODY_SIZE)
                n += 1
            a += 1
            if doc.page_count > target_end:
                break
    if with_toc:
        doc.set_toc(toc)
    doc.save(path, garbage=3, deflate=True)
    doc.close()
    return path


def _scanned(path: Path, pages: int = 5) -> Path:
    src = pymupdf.open()
    w = _Writer(src)
    for i in range(pages):
        w.new_page()
        w.block(f"Tema {i + 1}. Página escaneada", 18, bold=True)
        for n in range(4):
            w.block(_paragraph("célula", "membrana plasmática", n + i), BODY_SIZE)
    out = pymupdf.open()
    for page in src:
        pix = page.get_pixmap(dpi=100)
        dst = out.new_page(width=page.rect.width, height=page.rect.height)
        dst.insert_image(dst.rect, pixmap=pix)
    out.save(path, garbage=3, deflate=True)
    return path


def _protected(path: Path) -> Path:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Contenido protegido", fontsize=12)
    doc.save(
        path,
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        user_pw="secreto",
        owner_pw="propietario",
    )
    return path


def _damaged(path: Path) -> Path:
    path.write_bytes(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj << /Type /Catalog basura sin cerrar")
    return path


def build_all(folder: Path) -> Fixtures:
    """Genera los seis PDF de prueba en ``folder``."""
    folder.mkdir(parents=True, exist_ok=True)
    return Fixtures(
        con_indice=_book(folder / "con_indice.pdf", chapters=3, pages_per_chapter=8, with_toc=True),
        sin_indice=_book(
            folder / "sin_indice.pdf", chapters=3, pages_per_chapter=8, with_toc=False
        ),
        escaneado=_scanned(folder / "escaneado.pdf"),
        protegido=_protected(folder / "protegido.pdf"),
        danado=_damaged(folder / "danado.pdf"),
        largo=_book(folder / "largo.pdf", chapters=25, pages_per_chapter=20, with_toc=True),
    )


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent
    for name, p in vars(build_all(out)).items():
        print(f"{name:12} {p}")
