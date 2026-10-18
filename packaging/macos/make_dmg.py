"""Empaqueta ``dist/Criba.app`` en ``dist/Criba-<versión>-<arquitectura>.dmg`` (solo macOS).

Uso, tras PyInstaller: ``uv run python packaging/macos/make_dmg.py``. El disco lleva la app
y un acceso a Aplicaciones para instalarla arrastrándola.
"""

import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from criba import __version__

ARCH_NAMES = {"arm64": "AppleSilicon", "x86_64": "Intel"}


def dmg_name(version: str, machine: str) -> str:
    """``Criba-1.0.0-AppleSilicon.dmg``: el nombre dice para qué Mac es."""
    return f"Criba-{version}-{ARCH_NAMES[machine]}.dmg"


def main() -> int:
    """Crea el .dmg con hdiutil."""
    app = ROOT / "dist" / "Criba.app"
    if not app.is_dir():
        print("Falta dist/Criba.app: ejecuta antes PyInstaller.", file=sys.stderr)
        return 1
    out = ROOT / "dist" / dmg_name(__version__, platform.machine())
    out.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp) / "Criba"
        stage.mkdir()
        # symlinks=True: copia los enlaces de los frameworks tal cual (y no rompe la firma).
        shutil.copytree(app, stage / "Criba.app", symlinks=True)
        (stage / "Aplicaciones").symlink_to("/Applications")
        cmd = ["hdiutil", "create", "-volname", "Criba", "-srcfolder", str(stage)]
        subprocess.run([*cmd, "-format", "UDZO", "-ov", str(out)], check=True)
    print(out.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
