"""Ejecuta la autocomprobación de una app ya empaquetada e imprime su informe.

Uso (en el CI): ``python packaging/selftest_frozen.py <ruta al ejecutable>``. Quita del
entorno las variables de Python para que la app solo pueda usar lo que lleva dentro.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

TIMEOUT_S = 300
PYTHON_VARS = ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "QT_QPA_PLATFORM", "QML2_IMPORT_PATH")


def main() -> int:
    """Lanza el ejecutable con ``CRIBA_SELFTEST`` y devuelve su código de salida."""
    exe = Path(sys.argv[1])
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "informe.json"
        env = {k: v for k, v in os.environ.items() if k not in PYTHON_VARS}
        env["CRIBA_SELFTEST"] = str(report)
        code = subprocess.run([str(exe)], env=env, timeout=TIMEOUT_S, check=False).returncode
        if not report.exists():
            print(f"{exe} no ha escrito el informe (código {code}).", file=sys.stderr)
            return code or 1
        data = json.loads(report.read_text(encoding="utf-8"))
    for check in data["checks"]:
        print(f"[{'ok' if check['ok'] else 'FALLO'}] {check['name']}: {check['detail']}")
    if not data["frozen"]:
        print("No es la app empaquetada.", file=sys.stderr)
        return 1
    return code


if __name__ == "__main__":
    sys.exit(main())
