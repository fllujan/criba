"""Garantiza la separación por capas del spec §5: core/ y render/ sin Qt."""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).parent.parent / "src" / "criba"
QT_FREE = ["core", "render"]


@pytest.mark.parametrize("pkg", QT_FREE)
def test_no_qt_imports_in_source(pkg: str) -> None:
    for py in (SRC / pkg).rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            assert not any(n.startswith("PySide6") for n in names), f"{py} importa Qt"


def test_importing_core_does_not_load_qt() -> None:
    code = (
        "import sys, criba.core, criba.render, criba.cli, criba.logs, criba.paths;"
        "import pkgutil, importlib;"
        "[importlib.import_module(m.name) for p in (criba.core, criba.render)"
        " for m in pkgutil.walk_packages(p.__path__, p.__name__ + '.')];"
        "assert not any(k.startswith('PySide6') for k in sys.modules), 'Qt cargado'"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
