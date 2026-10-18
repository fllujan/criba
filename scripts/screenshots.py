"""Capturas de todas las pantallas con la IA simulada (para revisar el diseño).

Uso: ``uv run python scripts/screenshots.py salida/ [--dark] [--size 1200x780]``
No usa la clave real ni el llavero del sistema.
"""

import argparse
import os
import sys
import tempfile
import threading
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["CRIBA_HOME"] = tempfile.mkdtemp(prefix="criba-shots-")

import keyring
import keyring.backend
from PySide6.QtCore import QCoreApplication, QElapsedTimer, QtMsgType, qInstallMessageHandler
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickItem
from PySide6.QtQuickControls2 import QQuickStyle

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.fixtures.build import build_all

from criba import paths
from criba.core.cache import Cache
from criba.core.fake_llm import FakeLLMClient
from criba.gui.backend import Backend
from criba.gui.main_window import create_engine, load_fonts


class _Ring(keyring.backend.KeyringBackend):
    priority = 1  # type: ignore[assignment]

    def __init__(self) -> None:
        super().__init__()
        self.store: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.store.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.store[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        self.store.pop((service, username), None)


def wait(ms: int, until=None) -> None:
    timer = QElapsedTimer()
    timer.start()
    while timer.elapsed() < ms:
        QCoreApplication.processEvents()
        if until is not None and until():
            for _ in range(30):
                QCoreApplication.processEvents()
            return


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    parser.add_argument("--dark", action="store_true")
    parser.add_argument("--size", default="1200x780")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    w, h = (int(x) for x in args.size.split("x"))
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ["CRIBA_THEME"] = "dark" if args.dark else "light"
    keyring.set_keyring(_Ring())

    warnings: list[str] = []

    def handler(mode, _ctx, msg) -> None:
        if mode in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
            warnings.append(msg)

    qInstallMessageHandler(handler)
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication([])
    app.setApplicationVersion("0.1.0")
    load_fonts(app)
    fx = build_all(Path(tempfile.mkdtemp(prefix="criba-fx-")))
    gate = threading.Event()
    slow = {"on": False}

    def factory(key: str, model: str) -> FakeLLMClient:
        def fail(_r):
            if slow["on"]:
                gate.wait(30)

        return FakeLLMClient(model=model, fail=fail)

    with Cache(paths.cache_db()) as cache:
        backend = Backend(cache, llm_factory=factory, key_checker=lambda k, m: None)
        engine = create_engine(backend)
        if not engine.rootObjects():
            print("\n".join(warnings))
            return 2
        win = engine.rootObjects()[0]
        win.setWidth(w)
        win.setHeight(h)

        def shot(name: str) -> None:
            wait(450)
            win.grabWindow().save(str(args.out / f"{name}.png"))

        shot("01-setup")
        backend.testKey("sk-ant-demo-000000000000000000000000000000")
        wait(5000, lambda: backend.screen == "home")
        shot("02-home-empty")
        backend.openBook(fx.con_indice.as_uri())
        wait(10000, lambda: backend.hasBook and not backend.estimating)
        backend.subject = "Biología y Geología 1.º Bachillerato"
        backend.setChapterChecked(0, False)
        wait(3000, lambda: not backend.estimating)
        shot("03-home-book")
        chapter_list = win.findChild(QQuickItem, "chapterList")
        chapter_list.setProperty("currentIndex", 1)
        chapter_list.forceActiveFocus()
        shot("03b-home-keyboard-focus")
        win.contentItem().forceActiveFocus()
        slow["on"] = True
        backend.start()
        wait(1500)
        shot("04-processing")
        gate.set()
        slow["on"] = False
        wait(20000, lambda: backend.screen == "done")
        wait(1500)
        shot("05-done")
        win.setProperty("overlay", "settings")
        shot("06-settings")
        win.setProperty("overlay", "history")
        backend.refreshHistory()
        shot("07-history")
        win.setProperty("overlay", "")
        backend.processAnother()
        backend.openBook(fx.protegido.as_uri())
        wait(5000, lambda: bool(backend.error))
        shot("08-home-error")
        backend.shutdown()
        del engine
    for w_ in warnings:
        print("AVISO:", w_)
    print(f"{len(warnings)} avisos; capturas en {args.out}")
    return 1 if warnings else 0


if __name__ == "__main__":
    sys.exit(main())
