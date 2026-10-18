"""Uso por línea de comandos (desarrollo y tests).

Ejemplo: ``python -m criba.cli libro.pdf --nivel normal --salida ./out``
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from criba import __version__, logs, paths

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


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada de la CLI. Devuelve el código de salida."""
    args = parse_args(argv)
    log = logs.setup()
    if not args.pdf.is_file():
        print(f"No se ha encontrado el archivo: {args.pdf}", file=sys.stderr)
        return 2
    salida = args.salida or paths.default_output_dir()
    log.info("CLI: %s nivel=%s examen=%s salida=%s", args.pdf, args.nivel, args.examen, salida)
    print("El procesamiento llega en la fase F2.", file=sys.stderr)
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
