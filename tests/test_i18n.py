"""La estructura de traducciones (.ts de Qt) está al día con la interfaz (spec §4)."""

import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts.update_translations import I18N, QML, sources


def _messages(ts: Path) -> set[str]:
    return {m.findtext("source") or "" for m in ET.parse(ts).getroot().iter("message")}


def test_translation_template_is_up_to_date(tmp_path: Path) -> None:
    fresh = tmp_path / "fresh.ts"
    subprocess.run(
        ["pyside6-lupdate", *sources(), "-ts", str(fresh)], check=True, capture_output=True
    )
    assert _messages(fresh) == _messages(I18N / "criba_en.ts"), (
        "Ejecuta: uv run python scripts/update_translations.py"
    )


def test_visible_qml_text_goes_through_qstr() -> None:
    """Ningún «text: "…"» con letras en QML sin qsTr (salvo el nombre de la app)."""
    literal = re.compile(
        r'\b(text|title|placeholderText|confirmText|cancelText|message)\s*:\s*"([^"]*[A-Za-zÁÉÍÓÚáéíóúñ][^"]*)"'
    )
    offenders = []
    for path in QML.rglob("*.qml"):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            m = literal.search(line)
            if m and m.group(2) != "Criba":
                offenders.append(f"{path.name}:{n}: {line.strip()}")
    assert not offenders, offenders
