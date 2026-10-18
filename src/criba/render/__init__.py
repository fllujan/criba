"""Generación de los PDF de salida. No importa Qt."""

import errno
from pathlib import Path

from criba.core.errors import CribaError, ErrorKind
from criba.core.schemas import Libro


def output_names(asignatura: str) -> tuple[str, str]:
    """Nombres del spec §7: «{Asignatura} - Resumen.pdf» y «… - Esquema de examen.pdf»."""
    from criba.core.pipeline import safe_filename  # noqa: PLC0415 (evita un ciclo de imports)

    base = safe_filename(asignatura)
    return f"{base} - Resumen.pdf", f"{base} - Esquema de examen.pdf"


def render_book(libro: Libro, out_dir: Path) -> tuple[Path, Path]:
    """Genera los dos PDF en ``out_dir``. Lanza ``CribaError`` si no se pueden guardar."""
    from criba.render import outline_pdf, summary_pdf  # noqa: PLC0415

    summary_name, outline_name = output_names(libro.asignatura)
    try:
        return (
            summary_pdf.render(libro, out_dir / summary_name),
            outline_pdf.render(libro, out_dir / outline_name),
        )
    except OSError as exc:
        kind = ErrorKind.DISK_FULL if exc.errno == errno.ENOSPC else ErrorKind.CANNOT_WRITE
        raise CribaError(kind, detail=repr(exc)) from exc
