"""Estimación de tokens y coste (RF-10) y cálculo del coste real.

Para actualizar precios, edita ``PRICES``. El tipo de cambio es fijo a propósito:
la app no consulta Internet para nada que no sea la API de Anthropic (RNF-03).
"""

import math
from dataclasses import dataclass, field

CHARS_PER_TOKEN = 3.5
USD_TO_EUR = 0.92  # actualízalo cuando cambie de forma apreciable


@dataclass(frozen=True, slots=True)
class Price:
    """Precio en dólares por millón de tokens."""

    input: float
    output: float
    cache_write: float  # escritura en caché de 5 min (1,25 × entrada)
    cache_read: float


PRICES: dict[str, Price] = {
    "claude-sonnet-5-5": Price(input=2.00, output=10.00, cache_write=2.50, cache_read=0.20),
    "claude-haiku-5-5": Price(input=0.10, output=0.50, cache_write=0.125, cache_read=0.01),
    "claude-opus-5-5": Price(input=4.00, output=20.00, cache_write=5.00, cache_read=0.20),
}
DEFAULT_MODEL = "claude-sonnet-5-5"

# --- Supuestos de la estimación (calibrar con ejecuciones reales, objetivo ±25 %) ---
WORDS_PER_PAGE = 450  # palabras de una página A4 del resumen, con recuadros y títulos
TOKENS_PER_WORD = 1.6  # español y JSON
MAP_OUTPUT_OVERHEAD = 700  # preguntas, paja y estructura JSON por fragmento
REDUCE_OUTPUT_RATIO = 0.8  # la síntesis condensa lo que recibe
BOOK_INPUT_PER_CHAPTER = 450
BOOK_OUTPUT = 1_500
# Calibrado con un libro real (314 págs., nivel completo, oct. 2026): la entrada real fue
# ~1,3 veces la estimada (el español gasta más tokens por carácter) y la salida ~1,25.
INPUT_TOKEN_FACTOR = 1.3  # solo para el coste; el troceo del libro no cambia
THINKING_FACTOR = 1.75  # razonamiento adaptativo (esfuerzo medio), se factura como salida
OCR_INPUT_PER_PAGE = 2_400  # imagen de A4 a 150 ppp
OCR_OUTPUT_PER_PAGE = 700
OCR_BATCH = 5
# Tiempo: la salida se genera a ~OUTPUT_TOKENS_PER_SECOND por llamada, con 4 llamadas a la vez.
OUTPUT_TOKENS_PER_SECOND = 170  # medido: 265.000 tokens en 6,6 min, 4 a la vez
CALL_LATENCY = 3.0  # segundos de cada llamada antes de empezar a responder
PARALLEL_CALLS = 4
LEVEL_PERCENT: dict[str, int] = {"esencial": 10, "normal": 15, "completo": 20}


def estimate_tokens(text: str) -> int:
    """Tokens aproximados: caracteres / 3,5, redondeando hacia arriba."""
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def target_words(pages: int, level: str) -> int:
    """Palabras objetivo del resumen para ``pages`` páginas del libro."""
    return max(60, round(pages * LEVEL_PERCENT[level] / 100 * WORDS_PER_PAGE))


@dataclass(slots=True)
class Usage:
    """Tokens consumidos (suma de una o varias llamadas)."""

    input: int = 0
    output: int = 0
    cache_write: int = 0
    cache_read: int = 0

    def __iadd__(self, other: "Usage") -> "Usage":
        self.input += other.input
        self.output += other.output
        self.cache_write += other.cache_write
        self.cache_read += other.cache_read
        return self

    def cost_usd(self, model: str) -> float:
        """Coste en dólares con los precios de ``model``."""
        p = PRICES[model]
        return (
            self.input * p.input
            + self.output * p.output
            + self.cache_write * p.cache_write
            + self.cache_read * p.cache_read
        ) / 1_000_000


def to_eur(usd: float) -> float:
    """Convierte dólares a euros con el tipo fijo."""
    return usd * USD_TO_EUR


@dataclass(frozen=True, slots=True)
class ChunkPlan:
    """Lo que hace falta saber de un fragmento para estimar."""

    tokens: int
    pages: int
    cached: bool = False


@dataclass(frozen=True, slots=True)
class ChapterPlan:
    """Fragmentos de un capítulo y si su síntesis ya está en caché."""

    chunks: list[ChunkPlan]
    cached: bool = False


@dataclass(slots=True)
class Estimate:
    """Estimación que se enseña antes de procesar (RF-10)."""

    model: str
    calls: int = 0
    cached_calls: int = 0
    usage: Usage = field(default_factory=Usage)
    # (llamadas pendientes, tokens de salida, llamadas a la vez) por etapa, en orden
    stages: list[tuple[int, int, int]] = field(default_factory=list)

    @property
    def usd(self) -> float:
        """Coste estimado en dólares."""
        return self.usage.cost_usd(self.model)

    @property
    def eur(self) -> float:
        """Coste estimado en euros."""
        return to_eur(self.usd)

    @property
    def seconds(self) -> float:
        """Tiempo estimado de lo que falta (lo que está en caché es instantáneo).

        Las etapas van una tras otra (OCR → fragmentos → capítulos → libro) y dentro
        de cada una hay como mucho ``PARALLEL_CALLS`` llamadas a la vez.
        """
        total = 0.0
        for calls, output, parallel in self.stages:
            if calls:
                busy = output / OUTPUT_TOKENS_PER_SECOND + calls * CALL_LATENCY
                total += busy / min(parallel, calls)
        return total


def estimate(
    *,
    model: str,
    level: str,
    system_tokens: int,
    chapters: list[ChapterPlan],
    book_cached: bool = False,
    ocr_batches: list[tuple[int, bool]] | None = None,
) -> Estimate:
    """Estima llamadas y coste. Lo que ya está en caché no cuesta nada.

    ``ocr_batches`` es una lista de (páginas del lote, ya en caché).
    """
    est = Estimate(model=model)
    map_outputs: list[int] = []
    # Etapas en el orden del pipeline: el OCR va lote a lote; el resto, 4 a la vez.
    work = {
        "ocr": [0, 0, 1],
        "map": [0, 0, PARALLEL_CALLS],
        "reduce": [0, 0, PARALLEL_CALLS],
        "book": [0, 0, 1],
    }

    def add(stage: str, inp: int, out: int, *, cached: bool) -> None:
        est.calls += 1
        if cached:
            est.cached_calls += 1
            return
        tokens = math.ceil(out * THINKING_FACTOR)
        est.usage += Usage(input=math.ceil(inp * INPUT_TOKEN_FACTOR), output=tokens)
        work[stage][0] += 1
        work[stage][1] += tokens

    for n, cached in ocr_batches or []:
        add("ocr", system_tokens + n * OCR_INPUT_PER_PAGE, n * OCR_OUTPUT_PER_PAGE, cached=cached)

    for chapter in chapters:
        if not chapter.chunks:
            continue
        outputs = []
        for ch in chapter.chunks:
            out = round(target_words(ch.pages, level) * TOKENS_PER_WORD) + MAP_OUTPUT_OVERHEAD
            outputs.append(out)
            add("map", system_tokens + ch.tokens, out, cached=ch.cached)
        reduce_in = sum(outputs)
        add(
            "reduce",
            system_tokens + reduce_in,
            round(reduce_in * REDUCE_OUTPUT_RATIO),
            cached=chapter.cached,
        )
        map_outputs.append(reduce_in)

    if map_outputs:
        add(
            "book",
            system_tokens + len(map_outputs) * BOOK_INPUT_PER_CHAPTER,
            BOOK_OUTPUT,
            cached=book_cached,
        )
    est.stages = [(c, o, par) for c, o, par in work.values()]
    return est
