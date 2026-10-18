"""Arranque de la interfaz gráfica: ``python -m criba``."""

import sys

from criba.gui.main_window import run


def main() -> int:
    """Lanza la app de escritorio."""
    return run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
