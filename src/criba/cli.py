"""Uso por línea de comandos (desarrollo y tests).

Ejemplo: ``python -m criba.cli libro.pdf --nivel normal --salida ./out``
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from criba import __version__, logs, paths
from criba.core import ingest, structure
from criba.core.errors import CribaError

NIVELES = ("esencial", "normal", "completo")
TIPOS_EXAMEN = ("test", "desarrollo", "mixto")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Interpreta los argumentos de la línea de comandos."""
    parser = argparse.ArgumentParser(
        prog="criba", description="Resume un libro en PDF para estudiar."
    )
    parser.add_argument("pdf", type=Path, help="PDF del libro")
    parser.add_argument("--nivel", choices=NIVELES, default="normal")
    parser.add_argument("--examen", choices=TIPOS_EXAMEN, default="mixto")
    parser.add_argument("--salida", type=Path, default=None, help="carpeta de salida")
    parser.add_argument("--version", action="version", version=f"criba {__version__}")
    return parser.parse_args(argv)


def _miles(n: int) -> str:
    """Número con separador de miles español: 12.345."""
    return f"{n:,}".replace(",", ".")


def _print_analysis(book: ingest.Book) -> None:
    """Muestra el análisis local (gratis): páginas, capítulos y fragmentos."""
    chapters = structure.detect_chapters(book)
    print(f"Asignatura: {book.info.title}")
    print(f"Páginas: {book.info.page_count}  ·  escaneadas: {len(book.scanned_pages)}")
    print(f"Capítulos ({chapters[0].source}):")
    total_chunks = total_tokens = 0
    for ch in chapters:
        chunks = structure.chunk_chapter(book, ch)
        tokens = sum(c.tokens for c in chunks)
        total_chunks += len(chunks)
        total_tokens += tokens
        print(
            f"  · {ch.title}  (pp. {ch.start_page}–{ch.end_page}, "
            f"{len(ch.sections)} apartados, {len(chunks)} fragmentos, ≈{_miles(tokens)} tokens)"
        )
    print(f"Total: {total_chunks} fragmentos, ≈{_miles(total_tokens)} tokens de entrada")


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada de la CLI. Devuelve el código de salida."""
    args = parse_args(argv)
    log = logs.setup()
    salida = args.salida or paths.default_output_dir()
    log.info("CLI: %s nivel=%s examen=%s salida=%s", args.pdf, args.nivel, args.examen, salida)
    try:
        book = ingest.open_book(args.pdf)
    except CribaError as err:
        log.warning("CLI rechaza %s: %s (%s)", args.pdf, err.kind.name, err.detail)
        print(err.message, file=sys.stderr)
        return 2
    _print_analysis(book)
    print("\nEl procesamiento con IA llega en la fase F2.", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
