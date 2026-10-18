"""Errores previstos (spec §8) con mensaje para el usuario y acciones posibles.

El mensaje es lenguaje normal; el detalle técnico solo va al log. La interfaz
traduce ``kind`` a su propio texto con ``qsTr``; ``message`` sirve a la CLI.
"""

from enum import Enum, StrEnum
from typing import cast


class Action(StrEnum):
    """Acciones que la interfaz ofrece junto al mensaje."""

    CHOOSE_OTHER_FILE = "elegir_otro_archivo"
    CHANGE_KEY = "cambiar_clave"
    OPEN_CONSOLE = "abrir_consola"
    RETRY = "reintentar"
    WAIT = "esperar"
    CANCEL = "cancelar"
    CHOOSE_OTHER_FOLDER = "elegir_otra_carpeta"


class ErrorKind(Enum):
    """Situaciones previstas: (mensaje, acciones)."""

    NOT_FOUND = ("No se ha encontrado el archivo.", (Action.CHOOSE_OTHER_FILE,))
    PASSWORD_PROTECTED = (
        "Este PDF está protegido con contraseña.",
        (Action.CHOOSE_OTHER_FILE,),
    )
    CORRUPT = ("No se ha podido abrir este archivo.", (Action.CHOOSE_OTHER_FILE,))
    TOO_MANY_PAGES = (
        "Este PDF tiene más de 1.500 páginas. Elige uno más corto o divídelo.",
        (Action.CHOOSE_OTHER_FILE,),
    )
    TOO_LARGE = (
        "Este PDF ocupa más de 500 MB. Elige uno más ligero.",
        (Action.CHOOSE_OTHER_FILE,),
    )
    NO_TEXT = ("No se ha encontrado texto en este PDF.", (Action.CHOOSE_OTHER_FILE,))
    INVALID_KEY = ("La clave de API no es válida o ha caducado.", (Action.CHANGE_KEY,))
    NO_CREDIT = (
        "Tu cuenta de Anthropic no tiene saldo suficiente.",
        (Action.OPEN_CONSOLE, Action.RETRY),
    )
    OFFLINE = ("No hay conexión a Internet. Lo procesado se ha guardado.", (Action.RETRY,))
    RATE_LIMITED = (
        "El servicio está saturado. Se reintentará automáticamente.",
        (Action.WAIT, Action.CANCEL),
    )
    DISK_FULL = ("No hay espacio para guardar el PDF.", (Action.CHOOSE_OTHER_FOLDER,))
    CANNOT_WRITE = (
        "No se puede guardar en esa carpeta. Elige otra.",
        (Action.CHOOSE_OTHER_FOLDER,),
    )
    SERVICE_ERROR = (
        "El servicio de IA ha rechazado la petición. Lo procesado se ha guardado.",
        (Action.RETRY,),
    )
    PROCESSING_FAILED = (
        "No se ha podido procesar el libro. Lo procesado se ha guardado.",
        (Action.RETRY,),
    )
    RENDER_FAILED = (
        "No se han podido generar los PDF. Lo procesado se ha guardado.",
        (Action.RETRY,),
    )
    NO_KEY = (
        "Falta la clave de API de Anthropic. Añádela en Ajustes.",
        (Action.CHANGE_KEY,),
    )

    @property
    def message(self) -> str:
        """Mensaje en lenguaje normal."""
        return cast(str, self.value[0])

    @property
    def actions(self) -> tuple[Action, ...]:
        """Acciones que se ofrecen al usuario."""
        return cast(tuple[Action, ...], self.value[1])


class Cancelled(Exception):  # noqa: N818 (es un evento, no un error)
    """El usuario ha cancelado. Lo procesado está en la caché."""


class CribaError(Exception):
    """Error previsto. ``str()`` es el mensaje amable; ``detail`` va al log."""

    def __init__(self, kind: ErrorKind, detail: str = "") -> None:
        super().__init__(kind.message)
        self.kind = kind
        self.detail = detail
        self.usage: object | None = None  # tokens ya gastados (``cost.Usage``), si los hay

    @property
    def message(self) -> str:
        """Mensaje para el usuario."""
        return self.kind.message

    @property
    def actions(self) -> tuple[Action, ...]:
        """Acciones disponibles."""
        return self.kind.actions
