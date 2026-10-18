"""Ventana principal: crea el motor QML y arranca la app."""

import logging
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import QLocale, QTranslator, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from criba import __version__, logs

QML_DIR = Path(__file__).parent / "qml"
I18N_DIR = Path(__file__).parent.parent / "assets" / "i18n"

log = logging.getLogger(__name__)


def _install_translator(app: QGuiApplication) -> QTranslator | None:
    """Carga ``criba_<idioma>.qm`` si existe; el idioma base es el español."""
    translator = QTranslator(app)
    if translator.load(QLocale.system(), "criba", "_", str(I18N_DIR)):
        app.installTranslator(translator)
        return translator
    return None


def create_engine() -> QQmlApplicationEngine:
    """Crea el motor QML y carga ``Main.qml``. Requiere una QGuiApplication."""
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(QML_DIR))
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
    _install_translator(app)
    engine = create_engine()
    if not engine.rootObjects():
        log.error("No se ha podido cargar la interfaz QML")
        return 1
    code = app.exec()
    del engine
    logs.shutdown()
    return code
