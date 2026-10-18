"""Actualiza los archivos de traducción (.ts) con los textos de la interfaz QML.

Uso: ``uv run python scripts/update_translations.py`` y luego traduce con Qt Linguist.
El idioma base es el español; ``criba_en.ts`` es la plantilla para el inglés.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QML = ROOT / "src" / "criba" / "gui" / "qml"
I18N = ROOT / "src" / "criba" / "assets" / "i18n"
LANGUAGES = ("en",)


def sources() -> list[str]:
    """Archivos con textos traducibles."""
    return sorted(str(p) for p in QML.rglob("*") if p.suffix in {".qml", ".js"})


def main() -> int:
    """Ejecuta pyside6-lupdate para cada idioma."""
    for lang in LANGUAGES:
        ts = I18N / f"criba_{lang}.ts"
        cmd = ["pyside6-lupdate", *sources(), "-no-obsolete", "-ts", str(ts)]
        if subprocess.run(cmd, check=False).returncode:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
