"""Empaquetado (F6): versión única, nombres de los instaladores y filtros del .spec."""

import importlib.util
import re
import tomllib
from pathlib import Path

import criba

ROOT = Path(__file__).resolve().parent.parent
PACKAGING = ROOT / "packaging"


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_one_version_everywhere() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == criba.__version__


def test_dmg_name_says_which_mac() -> None:
    make_dmg = _load(PACKAGING / "macos" / "make_dmg.py")
    assert make_dmg.dmg_name("1.0.0", "arm64") == "Criba-1.0.0-AppleSilicon.dmg"
    assert make_dmg.dmg_name("1.0.0", "x86_64") == "Criba-1.0.0-Intel.dmg"


def _spec_filter():
    """La regex de módulos Qt que el .spec quita."""
    source = (PACKAGING / "criba.spec").read_text(encoding="utf-8")
    block = re.search(r"QT_UNUSED_FILES = re\.compile\((.*?),\s*re\.IGNORECASE", source, re.S)
    assert block
    pattern = "".join(re.findall(r'r"([^"]*)"', block[1]))
    return re.compile(pattern, re.IGNORECASE)


def test_spec_keeps_the_qml_modules_the_app_imports() -> None:
    unused = _spec_filter()
    imports = set()
    for qml in (ROOT / "src" / "criba" / "gui" / "qml").rglob("*.qml"):
        imports |= set(re.findall(r"^import (Qt[\w.]*)", qml.read_text(encoding="utf-8"), re.M))
    assert imports  # QtQuick, QtQuick.Controls.Basic, …
    for module in imports:
        path = "PySide6/Qt/qml/" + module.replace(".", "/") + "/qmldir"
        assert not unused.search(path), module
    assert not unused.search("PySide6/Qt/qml/QtQuick/Controls/Basic/impl/qmldir")
    assert not unused.search("pymupdf/libmupdf.dylib")  # «Pdf» de Qt, no PyMuPDF


def test_spec_drops_web_engine() -> None:
    unused = _spec_filter()
    assert unused.search("PySide6/Qt/lib/QtWebEngineCore.framework/QtWebEngineCore")
    assert unused.search("PySide6/Qt6WebEngineCore.dll")
    assert unused.search("PySide6/Qt/qml/QtQuick/Controls/Material/qmldir")


def test_installer_and_bundle_use_the_icons() -> None:
    iss = (PACKAGING / "windows" / "criba.iss").read_bytes()
    assert iss.startswith(b"\xef\xbb\xbf")  # UTF-8 con BOM: Inno Setup lee bien «Luján»
    assert b"SetupIconFile=criba.ico" in iss
    spec = (PACKAGING / "criba.spec").read_text(encoding="utf-8")
    assert "criba.icns" in spec
    assert "criba.ico" in spec
