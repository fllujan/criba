"""Autocomprobación de la app empaquetada (F6). La usa el CI, no el usuario.

``CRIBA_SELFTEST=<informe.json> Criba`` hace, sin red y sin tocar las carpetas reales:

- **pipeline**: crea un PDF pequeño y lo procesa entero con la IA simulada (lectura,
  prompts, caché, ReportLab y fuentes) y abre los dos PDF generados.
- **interfaz**: carga ``Main.qml`` y falla con cualquier aviso de QML (p. ej. un módulo
  que PyInstaller no ha empaquetado).
- **llavero**: comprueba que hay un llavero del sistema. Nunca lee la clave guardada:
  las otras comprobaciones usan un llavero vacío en memoria.

Escribe el informe en JSON (en Windows la app no tiene consola) y devuelve 0 si todo va bien.
"""

import json
import os
import sys
import tempfile
import traceback
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import keyring
import keyring.backend
import keyring.errors
import pymupdf
from keyring.compat import properties
from PySide6.QtCore import (
    QCoreApplication,
    QElapsedTimer,
    QMessageLogContext,
    QtMsgType,
    qInstallMessageHandler,
)
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuickControls2 import QQuickStyle

from criba import __version__, settings
from criba.core import pipeline
from criba.core.cache import Cache
from criba.core.fake_llm import FakeLLMClient
from criba.core.pipeline import Options, prepare

UI_WAIT_MS = 1500
CHAPTERS = ("La célula", "Genética")


@contextmanager
def _private_home() -> Iterator[Path]:
    """``CRIBA_HOME`` en una carpeta temporal mientras dura la comprobación."""
    old = os.environ.get("CRIBA_HOME")
    with tempfile.TemporaryDirectory(prefix="criba-selftest-") as tmp:
        os.environ["CRIBA_HOME"] = tmp
        try:
            yield Path(tmp)
        finally:
            if old is None:
                del os.environ["CRIBA_HOME"]
            else:
                os.environ["CRIBA_HOME"] = old


class _NoKeys(keyring.backend.KeyringBackend):
    """Llavero vacío en memoria: la autocomprobación nunca toca la clave guardada."""

    @properties.classproperty
    def priority(self) -> float:
        """No apto para el descubrimiento de keyring: solo se instala a mano."""
        raise RuntimeError("solo para la autocomprobación")

    def get_password(self, service: str, username: str) -> None:
        """Nunca hay clave."""

    def set_password(self, service: str, username: str, password: str) -> None:
        """No guarda nada."""
        raise keyring.errors.PasswordSetError("autocomprobación")

    def delete_password(self, service: str, username: str) -> None:
        """No hay nada que borrar."""
        raise keyring.errors.PasswordDeleteError("autocomprobación")


@contextmanager
def _no_saved_key() -> Iterator[None]:
    """Sustituye el llavero mientras dura la comprobación.

    En el Mac, leer la clave desde una app con otra firma abre un aviso del sistema y la
    app se queda esperando a que alguien responda.
    """
    real = keyring.get_keyring()
    keyring.set_keyring(_NoKeys())  # type: ignore[no-untyped-call]  # keyring sin tipos
    try:
        yield
    finally:
        keyring.set_keyring(real)


def _sample_book(path: Path) -> Path:
    """Libro de cuatro páginas con índice interno."""
    doc = pymupdf.open()
    toc: list[list[object]] = []
    text = (
        "Se denomina {t} al conjunto de procesos que estudia la biología. Es importante "
        "destacar que este concepto aparece en el examen con frecuencia. "
    ) * 8
    for title in CHAPTERS:
        toc.append([1, title, doc.page_count + 1])
        for i in range(2):
            page = doc.new_page()
            page.insert_textbox(pymupdf.Rect(72, 72, 520, 760), f"{title} {i + 1}\n\n" + text)
    doc.set_toc(toc)
    doc.save(path)
    doc.close()
    return path


def check_pipeline() -> str:
    """Procesa un libro de prueba con la IA simulada y abre los dos PDF."""
    with _private_home() as home, _no_saved_key():
        pdf = _sample_book(home / "libro.pdf")
        options = Options(asignatura="Autocomprobación", output_dir=home / "salida")
        model = settings.load().model
        with Cache(home / "cache.sqlite3") as cache:
            prep = prepare(pdf, options, cache, model)
            result = pipeline.run(prep, options, FakeLLMClient(model=model), cache)
        pages = []
        for out in (result.summary_pdf, result.outline_pdf):
            with pymupdf.open(out) as doc:
                if doc.page_count == 0 or not doc.get_toc():
                    raise RuntimeError(f"{out.name} sin páginas o sin marcadores")
                pages.append(doc.page_count)
    return f"{len(prep.chapters)} capítulos; PDF de {pages[0]} y {pages[1]} páginas"


def check_ui() -> str:
    """Carga la interfaz y falla con cualquier aviso de QML."""
    from criba.gui.backend import Backend  # noqa: PLC0415 (tras crear la app)
    from criba.gui.main_window import create_engine, load_fonts  # noqa: PLC0415

    app = QGuiApplication.instance()
    if not isinstance(app, QGuiApplication):
        raise TypeError("hace falta una QGuiApplication")
    problems: list[str] = []

    def handler(kind: QtMsgType, _ctx: QMessageLogContext, message: str) -> None:
        if kind != QtMsgType.QtDebugMsg and "qml" in message.lower():
            problems.append(message)

    previous = qInstallMessageHandler(handler)
    try:
        with _private_home() as home, _no_saved_key(), Cache(home / "cache.sqlite3") as cache:
            load_fonts(app)
            backend = Backend(cache)
            engine = create_engine(backend)
            timer = QElapsedTimer()
            timer.start()
            while timer.elapsed() < UI_WAIT_MS:  # deja que terminen los Loader
                QCoreApplication.processEvents()
            roots = len(engine.rootObjects())
            backend.shutdown()
            del engine
    finally:
        qInstallMessageHandler(previous)
    if not roots or problems:
        raise RuntimeError("; ".join(problems) or "no se ha cargado Main.qml")
    return "Main.qml cargado sin avisos"


def check_keyring() -> str:
    """Hay un llavero del sistema donde guardar la clave (sin leer ninguna entrada)."""
    backend = keyring.get_keyring()
    chain = getattr(backend, "backends", [backend])  # ChainerBackend encadena varios
    names = [f"{type(b).__module__}.{type(b).__name__}" for b in chain]
    usable = [n for n in names if "fail" not in n and "null" not in n]
    if not usable:
        raise RuntimeError(f"sin llavero del sistema ({', '.join(names) or 'ninguno'})")
    return ", ".join(usable)


def run(report: Path) -> int:
    """Hace las comprobaciones, escribe el informe y devuelve el código de salida."""
    if QCoreApplication.instance() is None:
        QQuickStyle.setStyle("Basic")
        app = QGuiApplication(sys.argv)  # noqa: F841 (vive mientras dura run)
    checks: list[tuple[str, Callable[[], str]]] = [
        ("pipeline", check_pipeline),
        ("interfaz", check_ui),
        ("llavero", check_keyring),
    ]
    results = []
    for name, check in checks:
        try:
            results.append({"name": name, "ok": True, "detail": check()})
        except Exception as exc:
            detail = "".join(traceback.format_exception_only(exc)).strip()
            results.append({"name": name, "ok": False, "detail": detail})
    ok = all(r["ok"] for r in results)
    data = {
        "version": __version__,
        "frozen": bool(getattr(sys, "frozen", False)),
        "ok": ok,
        "checks": results,
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if ok else 1
