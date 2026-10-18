"""Trabajo en segundo plano: un ``QThread`` que ejecuta una función del núcleo.

La ventana nunca espera al núcleo (RNF-01): leer el libro, estimar, procesar con la
IA o comprobar la clave corren aquí, y el resultado vuelve por señales, que Qt
entrega en el hilo de la interfaz.
"""

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, QThread, Signal

log = logging.getLogger(__name__)

Report = Callable[[object], None]
Job = Callable[[Report], object]


class Task(QThread):
    """Ejecuta ``job(report)`` en otro hilo. ``report`` emite ``progressed``."""

    progressed = Signal(object)
    succeeded = Signal(object)
    failed = Signal(object)

    def __init__(self, job: Job, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._job = job

    def run(self) -> None:
        """Cuerpo del hilo: nunca deja escapar una excepción."""
        try:
            result = self._job(self.progressed.emit)
        except BaseException as exc:
            self.failed.emit(exc)
        else:
            self.succeeded.emit(result)
