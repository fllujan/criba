"""Arranque de la interfaz gráfica: ``python -m criba``."""

import os
import sys
from pathlib import Path

from criba.gui.main_window import run


def main() -> int:
    """Lanza la app de escritorio (o su autocomprobación, si lo pide el CI)."""
    if report := os.environ.get("CRIBA_SELFTEST"):
        from criba.gui import selftest  # noqa: PLC0415 (solo en el CI)

        return selftest.run(Path(report))
    return run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
