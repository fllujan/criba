"""Modelos Pydantic de las respuestas de la IA y del resultado final (spec §6).

Las respuestas se piden con salidas estructuradas (``output_config.format``), que
no admiten esquemas recursivos: por eso el esquema jerárquico usa tres tipos
explícitos (``NodoEsquema`` → ``NodoMedio`` → ``NodoHoja``), lo que además
garantiza el máximo de 3 niveles del spec.

Las páginas se validan contra el rango del fragmento o capítulo, que se pasa como
contexto de validación: ``Modelo.model_validate_json(texto, context={"paginas": (a, b)})``.
Si una página cae fuera, la validación falla y la IA recibe el error para corregirlo.
"""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator, model_validator

MAX_CITA_PALABRAS = 40
OPCIONES_TEST = 4

TipoConcepto = Literal[
    "definicion", "idea_clave", "formula", "fecha", "clasificacion", "proceso", "autor", "dato"
]
TipoPregunta = Literal["test", "corta", "desarrollo", "problema"]
Prioridad = Literal["alta", "media", "baja"]
Nivel = Literal["esencial", "normal", "completo"]
TipoExamen = Literal["test", "desarrollo", "mixto"]


class _Modelo(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _check_pages(paginas: list[int], info: ValidationInfo) -> list[int]:
    if not paginas:
        raise ValueError("indica al menos una página (las marcas [p. N] del texto)")
    rango = (info.context or {}).get("paginas")
    if rango is not None:
        inicio, fin = rango
        fuera = [p for p in paginas if not inicio <= p <= fin]
        if fuera:
            raise ValueError(
                f"las páginas {fuera} no están en el texto recibido (pp. {inicio}–{fin})"
            )
    return sorted(set(paginas))


class Concepto(_Modelo):
    """Idea que hay que estudiar."""

    titulo: str
    explicacion: str  # 1-3 frases, en palabras propias
    tipo: TipoConcepto
    importancia: Literal[1, 2, 3]  # 3 = imprescindible
    paginas: list[int]
    cita_literal: str | None  # solo definiciones y fórmulas, máx. 40 palabras

    @field_validator("paginas")
    @classmethod
    def _paginas(cls, v: list[int], info: ValidationInfo) -> list[int]:
        return _check_pages(v, info)

    @field_validator("cita_literal")
    @classmethod
    def _cita(cls, v: str | None) -> str | None:
        if v is None or not v.strip():
            return None
        palabras = v.split()
        if len(palabras) > MAX_CITA_PALABRAS:
            return " ".join(palabras[:MAX_CITA_PALABRAS]) + " […]"
        return v.strip()


class PreguntaProbable(_Modelo):
    """Pregunta que puede caer en el examen (es una deducción: ``motivo`` la justifica)."""

    pregunta: str
    tipo: TipoPregunta
    respuesta_clave: str  # guion de respuesta, 2-5 frases
    opciones: list[str] | None  # 4 opciones si tipo == "test"
    correcta: int | None  # índice 0-3 de la opción correcta
    paginas: list[int]
    motivo: str  # por qué es probable

    @field_validator("paginas")
    @classmethod
    def _paginas(cls, v: list[int], info: ValidationInfo) -> list[int]:
        return _check_pages(v, info)

    @model_validator(mode="after")
    def _test(self) -> Self:
        if self.tipo == "test":
            if self.opciones is None or len(self.opciones) != OPCIONES_TEST:
                raise ValueError("una pregunta tipo test necesita exactamente 4 opciones")
            if self.correcta is None or not 0 <= self.correcta < OPCIONES_TEST:
                raise ValueError("una pregunta tipo test necesita 'correcta' entre 0 y 3")
        else:
            self.opciones = None
            self.correcta = None
        return self


class ChunkAnalysis(_Modelo):
    """Resultado de analizar un fragmento (etapa map)."""

    conceptos: list[Concepto]
    preguntas: list[PreguntaProbable]
    paja: list[str]  # qué se ha descartado, en una línea cada cosa


class NodoHoja(_Modelo):
    """Tercer nivel del esquema."""

    texto: str
    negrita: list[str]  # palabras clave del texto que van en negrita
    paginas: list[int]

    @field_validator("paginas")
    @classmethod
    def _paginas(cls, v: list[int], info: ValidationInfo) -> list[int]:
        return _check_pages(v, info)


class NodoMedio(NodoHoja):
    """Segundo nivel del esquema."""

    hijos: list[NodoHoja]


class NodoEsquema(NodoHoja):
    """Primer nivel del esquema jerárquico (máx. 3 niveles)."""

    hijos: list[NodoMedio]


class SintesisCapitulo(_Modelo):
    """Lo que devuelve la IA al fusionar los fragmentos de un capítulo (etapa reduce)."""

    prioridad: Prioridad
    resumen: str  # 1 párrafo
    esquema: list[NodoEsquema]
    conceptos: list[Concepto]
    preguntas: list[PreguntaProbable]
    paja: list[str]


class SintesisLibro(_Modelo):
    """Mapa general del libro y conexiones entre temas."""

    mapa: str
    conexiones: list[str]


class OcrPagina(_Modelo):
    """Texto de una página escaneada."""

    pagina: int
    texto: str


class OcrResultado(_Modelo):
    """Resultado del OCR de un lote de páginas."""

    paginas: list[OcrPagina]

    @model_validator(mode="after")
    def _todas(self, info: ValidationInfo) -> Self:
        esperadas = (info.context or {}).get("paginas_ocr")
        if esperadas is not None:
            recibidas = {p.pagina for p in self.paginas}
            faltan = sorted(set(esperadas) - recibidas)
            if faltan:
                raise ValueError(f"faltan las páginas {faltan}")
        return self


class Capitulo(_Modelo):
    """Capítulo final, tal como lo usan los PDF."""

    titulo: str
    paginas: tuple[int, int]
    prioridad: Prioridad
    resumen: str
    esquema: list[NodoEsquema]
    conceptos: list[Concepto]
    preguntas: list[PreguntaProbable]
    paja: list[str]  # para «Lo que puedes saltarte»
    ha_caido_en_examen: bool


class Libro(_Modelo):
    """Resultado final del pipeline: la entrada de los dos PDF (sección 7)."""

    version: Literal[1] = 1
    asignatura: str
    titulo_libro: str
    archivo: str
    sha256: str
    paginas_libro: int
    nivel: Nivel
    tipo_examen: TipoExamen
    idioma: str
    modelo: str
    fecha: str  # ISO 8601
    mapa: str
    conexiones: list[str]
    capitulos: list[Capitulo]
    paginas_no_procesadas: list[tuple[int, int]]  # RNF-05
    paginas_ocr: list[int]
    coste_usd: float
