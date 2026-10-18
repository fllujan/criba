"""Generación de los PDF de salida. No importa Qt."""

import contextlib
import errno
import logging
import uuid
from pathlib import Path

from criba.core.errors import CribaError, ErrorKind
from criba.core.schemas import Libro

log = logging.getLogger(__name__)


def output_names(asignatura: str) -> tuple[str, str]:
    """Nombres del spec §7: «{Asignatura} - Resumen.pdf» y «… - Esquema de examen.pdf»."""
    from criba.core.pipeline import safe_filename  # noqa: PLC0415 (evita un ciclo de imports)

    base = safe_filename(asignatura)
    return f"{base} - Resumen.pdf", f"{base} - Esquema de examen.pdf"


def render_book(libro: Libro, out_dir: Path) -> tuple[Path, Path]:
    """Genera los dos PDF en ``out_dir``. Lanza ``CribaError`` si algo falla.

    Los dos se escriben primero en archivos temporales y solo se sustituyen los
    anteriores cuando ambos están listos: nunca queda una pareja a medias.
    """
    from criba.render import outline_pdf, summary_pdf  # noqa: PLC0415

    finals = [out_dir / name for name in output_names(libro.asignatura)]
    # Nombres temporales únicos: dos generaciones a la vez no se pisan.
    tag = uuid.uuid4().hex[:8]
    temps = [p.with_name(f".{p.name}.{tag}.tmp") for p in finals]
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        summary_pdf.render(libro, temps[0])
        outline_pdf.render(libro, temps[1])
        for tmp, final in zip(temps, finals, strict=True):
            tmp.replace(final)
    except OSError as exc:
        _cleanup(temps)
        kind = ErrorKind.DISK_FULL if exc.errno == errno.ENOSPC else ErrorKind.CANNOT_WRITE
        raise CribaError(kind, detail=repr(exc)) from exc
    except Exception as exc:  # LayoutError u otros fallos de ReportLab
        _cleanup(temps)
        log.exception("Fallo al generar los PDF")
        raise CribaError(ErrorKind.RENDER_FAILED, detail=repr(exc)) from exc
    return finals[0], finals[1]


def _cleanup(paths: list[Path]) -> None:
    for p in paths:
        with contextlib.suppress(OSError):
            p.unlink(missing_ok=True)
