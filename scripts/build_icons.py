"""Genera los iconos de la app desde ``packaging/icon/*.svg``.

Uso: ``uv run python scripts/build_icons.py``. Escribe ``criba.icns`` (macOS),
``criba.ico`` (Windows) y ``criba.png`` (icono de ventana). Los archivos van al
repositorio para que el empaquetado no dependa de este script.

Los .ico y .icns se escriben aquí con PNG dentro (ambos formatos lo admiten), sin
herramientas propias de un solo sistema como ``iconutil``.
"""

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SVG = ROOT / "packaging" / "icon" / "criba.svg"
SVG_SMALL = ROOT / "packaging" / "icon" / "criba-small.svg"  # 16 y 32 px
SMALL = 32

# Tipo de cada imagen del .icns y su tamaño en píxeles (los @2x repiten tamaño).
ICNS_TYPES = {
    "icp4": 16,
    "icp5": 32,
    "ic11": 32,
    "ic12": 64,
    "ic07": 128,
    "ic08": 256,
    "ic13": 256,
    "ic09": 512,
    "ic14": 512,
    "ic10": 1024,
}
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
WINDOW_SIZE = 512


def outputs(root: Path) -> dict[str, Path]:
    """Dónde va cada archivo generado, relativo a ``root``."""
    return {
        "criba.icns": root / "packaging" / "macos" / "criba.icns",
        "criba.ico": root / "packaging" / "windows" / "criba.ico",
        "criba.png": root / "src" / "criba" / "assets" / "icons" / "criba.png",
    }


def write_ico(path: Path, pngs: dict[int, bytes]) -> None:
    """Escribe un .ico con una entrada PNG por tamaño."""
    header = struct.pack("<HHH", 0, 1, len(pngs))
    offset = len(header) + 16 * len(pngs)
    entries, blobs = b"", b""
    for size, png in pngs.items():
        side = 0 if size >= 256 else size  # noqa: PLR2004 (0 significa 256 en el formato)
        entries += struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(png), offset)
        blobs += png
        offset += len(png)
    path.write_bytes(header + entries + blobs)


def write_icns(path: Path, pngs: dict[int, bytes]) -> None:
    """Escribe un .icns con los tipos de ``ICNS_TYPES``."""
    body = b"".join(
        kind.encode() + struct.pack(">I", 8 + len(pngs[size])) + pngs[size]
        for kind, size in ICNS_TYPES.items()
    )
    path.write_bytes(b"icns" + struct.pack(">I", 8 + len(body)) + body)


def render(size: int) -> bytes:
    """El icono a ``size`` píxeles, en PNG. Requiere una QGuiApplication."""
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt  # noqa: PLC0415
    from PySide6.QtGui import QImage, QPainter  # noqa: PLC0415
    from PySide6.QtSvg import QSvgRenderer  # noqa: PLC0415

    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(str(SVG_SMALL if size <= SMALL else SVG)).render(painter)
    painter.end()
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(data.data())


def build(folder: Path) -> None:
    """Genera los tres archivos en ``folder`` con los nombres de ``outputs``."""
    sizes = sorted({*ICNS_TYPES.values(), *ICO_SIZES, WINDOW_SIZE})
    pngs = {s: render(s) for s in sizes}
    folder.mkdir(parents=True, exist_ok=True)
    write_icns(folder / "criba.icns", pngs)
    write_ico(folder / "criba.ico", {s: pngs[s] for s in ICO_SIZES})
    (folder / "criba.png").write_bytes(pngs[WINDOW_SIZE])


def main() -> int:
    """Genera los iconos y los copia a su sitio."""
    from PySide6.QtGui import QGuiApplication  # noqa: PLC0415

    app = QGuiApplication(sys.argv)  # noqa: F841 (QSvgRenderer necesita la app)
    tmp = ROOT / "build" / "icons"
    build(tmp)
    for name, dest in outputs(ROOT).items():
        dest.write_bytes((tmp / name).read_bytes())
        print(dest.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
