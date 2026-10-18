"""Ventana principal: crea el motor QML con el backend y arranca la app."""

import logging
import os
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import QLocale, QTranslator, QUrl
from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from criba import __version__, logs, paths
from criba.core.cache import Cache
from criba.gui.backend import Backend
from criba.gui.thumbs import ThumbnailProvider

QML_DIR = Path(__file__).parent / "qml"
ASSETS = Path(__file__).parent.parent / "assets"
I18N_DIR = ASSETS / "i18n"
FONTS_DIR = ASSETS / "fonts"

log = logging.getLogger(__name__)


def _install_translator(app: QGuiApplication) -> QTranslator | None:
    """Carga ``criba_<idioma>.qm`` si existe; el idioma base es el español."""
    translator = QTranslator(app)
    if translator.load(QLocale.system(), "criba", "_", str(I18N_DIR)):
        app.installTranslator(translator)
        return translator
    return None


def load_fonts(app: QGuiApplication) -> None:
    """Registra Inter y Source Serif 4 (las mismas que los PDF, iguales en Mac y Windows)."""
    for font in sorted(FONTS_DIR.glob("*.ttf")):
        # Desde los datos: en macOS registrar por ruta falla en algunos entornos.
        if QFontDatabase.addApplicationFontFromData(font.read_bytes()) < 0:
            log.warning("No se ha podido cargar la fuente %s", font.name)
    base = QFont(app.font())  # conserva el tamaño de letra del sistema
    base.setFamily("Inter")
    app.setFont(base)


def create_engine(backend: Backend) -> QQmlApplicationEngine:
    """Crea el motor QML y carga ``Main.qml``. Requiere una QGuiApplication."""
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(QML_DIR))
    engine.addImageProvider("thumb", ThumbnailProvider())
    theme = os.environ.get("CRIBA_THEME", "")  # desarrollo: forzar "light" o "dark"
    engine.setInitialProperties(
        {"backend": backend, "themeOverride": theme if theme in {"light", "dark"} else ""}
    )
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    return engine


def run(argv: Sequence[str]) -> int:
    """Arranca la app y devuelve el código de salida."""
    logs.setup()
    log.info("Arrancando Criba %s", __version__)
    QQuickStyle.setStyle("Basic")  # mismo aspecto en Mac y Windows
    app = QGuiApplication(list(argv))
    app.setApplicationName("Criba")
    app.setOrganizationName("Criba")
    app.setApplicationVersion(__version__)
    icon = ASSETS / "icons" / "criba.png"
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    _install_translator(app)
    load_fonts(app)
    with Cache(paths.cache_db()) as cache:
        backend = Backend(cache)
        engine = create_engine(backend)
        if not engine.rootObjects():
            log.error("No se ha podido cargar la interfaz QML")
            return 1
        code = app.exec()
        backend.shutdown()
        del engine
    logs.shutdown()
    return code
