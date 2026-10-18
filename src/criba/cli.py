"""Uso por línea de comandos (desarrollo y tests).

Ejemplo: ``python -m criba.cli libro.pdf --nivel normal --salida ./out``
"""

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from criba import __version__, logs, paths, settings
from criba.core import exams, ingest, structure
from criba.core.cache import Cache
from criba.core.cost import PRICES, to_eur
from criba.core.errors import Cancelled, CribaError, ErrorKind
from criba.core.fake_llm import FakeLLMClient
from criba.core.llm import AnthropicClient, LLMClient
from criba.core.pipeline import CancelToken, Options, Prepared, Progress, prepare, run
from criba.core.schemas import Libro
from criba.render import render_book

NIVELES = ("esencial", "normal", "completo")
TIPOS_EXAMEN = ("test", "desarrollo", "mixto")
STAGE_NAMES = {
    "leyendo": "Leyendo",
    "ocr": "Leyendo páginas escaneadas",
    "analizando": "Analizando",
    "sintetizando": "Sintetizando",
    "generando": "Generando",
    "listo": "Listo",
}


def _range(text: str) -> tuple[int, int]:
    try:
        a, b = (int(x) for x in text.replace("–", "-").split("-", 1))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("usa el formato 10-80") from exc
    if not 1 <= a <= b:
        raise argparse.ArgumentTypeError("el rango debe ser creciente y empezar en 1 o más")
    return a, b


def _chapters(text: str) -> tuple[int, ...]:
    try:
        return tuple(sorted({int(x) - 1 for x in text.split(",") if x.strip()}))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("usa números separados por comas: 1,3,4") from exc


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Interpreta los argumentos de la línea de comandos."""
    parser = argparse.ArgumentParser(
        prog="criba", description="Resume un libro en PDF para estudiar."
    )
    parser.add_argument(
        "pdf", type=Path, help="PDF del libro (o un «datos.json» para regenerar solo los PDF)"
    )
    parser.add_argument("--nivel", choices=NIVELES, default="normal")
    parser.add_argument("--examen", choices=TIPOS_EXAMEN, default="mixto")
    parser.add_argument("--salida", type=Path, default=None, help="carpeta de salida")
    parser.add_argument("--asignatura", default=None, help="por defecto, el título del PDF")
    parser.add_argument("--modelo", choices=sorted(PRICES), default=None)
    parser.add_argument(
        "--idioma", default=None, help="código: es, en… (por defecto, el del libro)"
    )
    parser.add_argument("--capitulos", type=_chapters, default=None, help="p. ej. 1,3,4")
    parser.add_argument("--paginas", type=_range, default=None, help="p. ej. 10-80")
    parser.add_argument(
        "--examenes", type=Path, nargs="+", default=[], help="PDF de exámenes antiguos (opcional)"
    )
    parser.add_argument("--solo-analisis", action="store_true", help="no llama a la IA")
    parser.add_argument("--simulado", action="store_true", help="IA simulada (gratis, para probar)")
    parser.add_argument("--si", action="store_true", help="no pide confirmación")
    parser.add_argument("--version", action="version", version=f"criba {__version__}")
    return parser.parse_args(argv)


def _miles(n: int) -> str:
    """Número con separador de miles español: 12.345."""
    return f"{n:,}".replace(",", ".")


def _euros(x: float) -> str:
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _print_analysis(prep: Prepared) -> None:
    """Muestra el análisis local (gratis) y la estimación (RF-10)."""
    book = prep.book
    print(f"Asignatura: {prep.study.asignatura}")
    print(
        f"Páginas: {book.info.page_count}  ·  escaneadas: {len(book.scanned_pages)}"
        f"  ·  idioma: {prep.language}"
    )
    print(f"Capítulos ({prep.chapters[0].source}):")
    selected = {(c.title, c.start_page) for c in prep.selected}
    for i, ch in enumerate(prep.chapters, 1):
        mark = "x" if any(t == ch.title for t, _ in selected) else " "
        chunks = structure.chunk_chapter(book, ch)
        tokens = sum(c.tokens for c in chunks)
        print(
            f"  [{mark}] {i}. {ch.title}  (pp. {ch.start_page}–{ch.end_page}, "
            f"{len(chunks)} fragmentos, ≈{_miles(tokens)} tokens)"
        )
    if prep.exams:
        print(f"Exámenes antiguos: {len(prep.exams)} ({', '.join(e.name for e in prep.exams)})")
    est = prep.estimate
    print(
        f"\nEstimación con {prep.model}: {est.calls} llamadas"
        f" ({est.cached_calls} ya en caché, gratis)"
        f" · ≈{_euros(est.eur)} € (≈{_euros(est.usd)} $)"
    )


def _progress(p: Progress) -> None:
    eta = f" · quedan ≈{round(p.eta_seconds / 60) or 1} min" if p.eta_seconds else ""
    cap = f" · capítulo {p.chapter} de {p.chapters}" if p.chapter and p.chapters else ""
    sys.stderr.write(
        f"\r{STAGE_NAMES[p.stage]}{cap} · {p.done}/{p.total}"
        f" · {_euros(to_eur(p.cost_usd))} €{eta}\033[K"
    )
    sys.stderr.flush()


def _client(args: argparse.Namespace, model: str) -> LLMClient:
    if args.simulado:
        return FakeLLMClient(model=model)
    key = settings.get_api_key()
    if not key:
        raise CribaError(ErrorKind.NO_KEY)
    return AnthropicClient(key, model)


def _render_only(json_path: Path, out_dir: Path | None) -> int:
    """Regenera los dos PDF a partir de un «datos.json» (sin IA, sin coste)."""
    try:
        libro = Libro.model_validate_json(json_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print(f"No se ha podido leer {json_path}.", file=sys.stderr)
        return 2
    try:
        summary, outline = render_book(libro, out_dir or json_path.parent)
    except CribaError as err:
        print(err.message, file=sys.stderr)
        return 2
    print(f"Resumen: {summary}\nEsquema: {outline}")
    return 0


def _exam_problem(paths: list[Path]) -> str | None:
    """Comprueba los exámenes antes de leer el libro; el mensaje dice cuál falla."""
    if len(paths) > exams.MAX_EXAMS:
        return ErrorKind.TOO_MANY_EXAMS.message
    found = []
    for exam in paths:
        try:
            found.append(exams.read_exam(exam))
        except CribaError as err:
            logging.getLogger("criba.cli").warning(
                "CLI: examen %s: %s (%s)", exam, err.kind.name, err.detail
            )
            return f"Examen «{exam.name}»: {err.message}"
    problem = exams.limits_problem(found)
    return problem.message if problem else None


def main(argv: Sequence[str] | None = None) -> int:  # noqa: PLR0911 (un código por caso)
    """Punto de entrada de la CLI. Devuelve el código de salida."""
    args = parse_args(argv)
    log = logs.setup()
    if args.pdf.suffix.lower() == ".json":
        return _render_only(args.pdf, args.salida)
    prefs = settings.load()
    model = args.modelo or prefs.model
    salida = args.salida or prefs.output_path
    log.info("CLI: %s nivel=%s examen=%s modelo=%s", args.pdf, args.nivel, args.examen, model)
    cancel = CancelToken()
    if problem := _exam_problem(args.examenes):
        print(problem, file=sys.stderr)
        return 2
    try:
        title = args.asignatura or ingest.validate(args.pdf).title
        options = Options(
            asignatura=title,
            nivel=args.nivel,
            tipo_examen=args.examen,
            idioma=args.idioma or prefs.language,
            chapters=args.capitulos,
            page_range=args.paginas,
            output_dir=salida,
            exams=tuple(args.examenes),
        )
        with Cache(paths.cache_db()) as cache:
            prep = prepare(args.pdf, options, cache, model)
            _print_analysis(prep)
            if args.solo_analisis:
                return 0
            if not args.si and input("\n¿Generar? [s/N] ").strip().lower() not in {"s", "si", "sí"}:
                print("No se ha procesado nada.")
                return 0
            result = run(
                prep, options, _client(args, model), cache, on_progress=_progress, cancel=cancel
            )
    except CribaError as err:
        log.warning("CLI: %s (%s)", err.kind.name, err.detail)
        print(f"\n{err.message}", file=sys.stderr)
        return 2
    except (KeyboardInterrupt, Cancelled):
        cancel.cancel()
        print("\nCancelado. Lo procesado se ha guardado y no se volverá a pagar.", file=sys.stderr)
        return 130
    print(
        f"\n\nResumen: {result.summary_pdf}\nEsquema: {result.outline_pdf}\n"
        f"Llamadas: {result.calls} ({result.cached_calls} desde la caché)"
        f" · coste real ≈{_euros(to_eur(result.cost_usd))} € ({_euros(result.cost_usd)} $)"
    )
    if result.exams_failed:
        print(
            "No se han podido analizar los exámenes: los PDF van sin «Ha caído en examen».",
            file=sys.stderr,
        )
    if result.failed_pages:
        rangos = ", ".join(f"{a}–{b}" for a, b in result.failed_pages)
        print(f"Páginas no procesadas: {rangos}", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
