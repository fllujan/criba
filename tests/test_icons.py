"""Iconos de la app (F6): formato de .ico/.icns y que los del repositorio están al día."""

import struct
from pathlib import Path

import pytest
from scripts import build_icons as bi

PNG = b"\x89PNG\r\n\x1a\n"


def _fake_png(size: int) -> bytes:
    return PNG + struct.pack(">II", size, size) + b"x" * size


def test_ico_has_one_png_entry_per_size(tmp_path: Path) -> None:
    sizes = (16, 32, 256)
    out = tmp_path / "a.ico"
    bi.write_ico(out, {s: _fake_png(s) for s in sizes})
    data = out.read_bytes()
    reserved, kind, count = struct.unpack_from("<HHH", data)
    assert (reserved, kind, count) == (0, 1, 3)
    for i, size in enumerate(sizes):
        w, h, _, _, planes, bpp, length, offset = struct.unpack_from("<BBBBHHII", data, 6 + 16 * i)
        assert (w or 256, h or 256, planes, bpp) == (size, size, 1, 32)
        assert data[offset : offset + length] == _fake_png(size)


def test_icns_lists_every_type_with_its_length(tmp_path: Path) -> None:
    out = tmp_path / "a.icns"
    bi.write_icns(out, {s: _fake_png(s) for s in bi.ICNS_TYPES.values()})
    data = out.read_bytes()
    assert data[:4] == b"icns"
    assert struct.unpack_from(">I", data, 4)[0] == len(data)
    pos, seen = 8, []
    while pos < len(data):
        kind, length = struct.unpack_from(">4sI", data, pos)
        assert data[pos + 8 : pos + 8 + len(PNG)] == PNG
        seen.append(kind.decode())
        pos += length
    assert pos == len(data)
    assert seen == list(bi.ICNS_TYPES)


def _pngs(path: Path) -> list[bytes]:
    """Los PNG que contiene un .png, .ico o .icns."""
    data = path.read_bytes()
    if path.suffix == ".png":
        return [data]
    if path.suffix == ".ico":
        count = struct.unpack_from("<H", data, 4)[0]
        entries = [struct.unpack_from("<II", data, 6 + 16 * i + 8) for i in range(count)]
        return [data[o : o + n] for n, o in entries]
    out, pos = [], 8
    while pos < len(data):
        length = struct.unpack_from(">I", data, pos + 4)[0]
        out.append(data[pos + 8 : pos + length])
        pos += length
    return out


def _close(a: bytes, b: bytes) -> bool:
    """Mismos píxeles salvo diferencias mínimas de antialiasing entre sistemas."""
    from PySide6.QtGui import QImage  # noqa: PLC0415 (solo este test usa Qt)

    ia, ib = (QImage.fromData(x).convertToFormat(QImage.Format.Format_ARGB32) for x in (a, b))
    if ia.size() != ib.size():
        return False
    pa, pb = bytes(ia.constBits()), bytes(ib.constBits())
    return sum(abs(x - y) for x, y in zip(pa, pb, strict=True)) / len(pa) < 1


@pytest.mark.gui
def test_committed_icons_match_the_svg(qapp, tmp_path: Path) -> None:
    """Si cambias el SVG, ejecuta ``uv run python scripts/build_icons.py``."""
    bi.build(tmp_path)
    for name, committed in bi.outputs(bi.ROOT).items():
        fresh, saved = _pngs(tmp_path / name), _pngs(committed)
        assert len(fresh) == len(saved), name
        assert all(_close(a, b) for a, b in zip(fresh, saved, strict=True)), name
