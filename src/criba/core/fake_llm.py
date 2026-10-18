"""``FakeLLMClient``: IA simulada para tests y para ``--simulado`` en la CLI.

No se conecta a nada ni gasta saldo. Construye respuestas válidas a partir del texto
que recibe, con páginas reales (las marcas ``[p. N]``), para que el pipeline entero
se pueda probar de principio a fin.
"""

import json
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any

from criba.core import schemas
from criba.core.cost import DEFAULT_MODEL, Usage, estimate_tokens
from criba.core.llm import Image, LLMCallError, LLMRequest, RawResponse

_PAGE = re.compile(r"^\[p\. (\d+)\]$")
_CHAPTER_LINE = re.compile(r"^(\d+)\. (.+)$")
_QUESTION = re.compile(r"^\d+[.)]\s+(.+)$")
_WORD = re.compile(r"\w{5,}")


@dataclass
class FakeLLMClient:
    """Cliente simulado. ``fail`` decide qué peticiones fallan (para probar errores)."""

    model: str = DEFAULT_MODEL
    fail: Callable[[LLMRequest], Exception | None] | None = None
    invalid_first: bool = False  # la primera respuesta de cada petición no cumple el esquema
    calls: list[LLMRequest] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def complete(self, request: LLMRequest) -> RawResponse:
        """Devuelve una respuesta coherente con la petición."""
        with self._lock:
            self.calls.append(request)
        if self.fail and (exc := self.fail(request)):
            raise exc
        if self.invalid_first and request.retry is None:
            text = '{"incompleto": true}'
        else:
            text = json.dumps(self._answer(request), ensure_ascii=False)
        prompt = request.system + "".join(c for c in request.content if isinstance(c, str))
        images = sum(1 for c in request.content if isinstance(c, Image))
        usage = Usage(input=estimate_tokens(prompt) + images * 2_400, output=estimate_tokens(text))
        return RawResponse(text=text, usage=usage, model=self.model, stop_reason="end_turn")

    def calls_for(self, schema: type) -> list[LLMRequest]:
        """Peticiones hechas con un esquema concreto."""
        return [c for c in self.calls if c.schema is schema]

    def _answer(self, request: LLMRequest) -> dict[str, Any]:
        text = "\n".join(c for c in request.content if isinstance(c, str))
        match request.schema:
            case schemas.ChunkAnalysis:
                return _chunk(text)
            case schemas.SintesisCapitulo:
                return _chapter(json.loads(request.content[-1]))  # type: ignore[arg-type]
            case schemas.SintesisLibro:
                return _book(json.loads(request.content[-1]))  # type: ignore[arg-type]
            case schemas.AnalisisExamenes:
                return _exams([c for c in request.content if isinstance(c, str)])
            case schemas.OcrResultado:
                return {
                    "paginas": [
                        {
                            "pagina": p,
                            "texto": f"Texto leído por OCR de la página {p}.\n\n"
                            f"La membrana plasmática regula el paso de sustancias (página {p}).",
                        }
                        for p in request.context["paginas_ocr"]
                    ]
                }
        raise LLMCallError(f"esquema no simulado: {request.schema.__name__}")


def _pages_and_paragraphs(text: str) -> list[tuple[int, str]]:
    """(página, párrafo) del fragmento; ignora la cabecera y el contexto de solapamiento."""
    out: list[tuple[int, str]] = []
    page: int | None = None
    for block in text.split("\n\n"):
        first, _, rest = block.partition("\n")
        body = block
        if m := _PAGE.match(first.strip()):
            page = int(m[1])
            body = rest
        if page is not None and body.strip():
            out.append((page, body.strip()))
    return out


def _chunk(text: str) -> dict[str, Any]:
    paras = _pages_and_paragraphs(text)
    conceptos: list[dict[str, Any]] = []
    for i, (page, para) in enumerate(paras[:12]):
        sentence = para.split(". ")[0].rstrip(".") + "."
        words = sentence.split()
        conceptos.append(
            {
                "titulo": " ".join(words[:6]).rstrip(",.;:"),
                "explicacion": sentence,
                "tipo": "definicion" if i % 3 == 0 else "idea_clave",
                "importancia": 3 if i % 3 == 0 else 2,
                "paginas": [page],
                "cita_literal": " ".join(words[:20]) if i % 3 == 0 else None,
            }
        )
    pages = sorted({p for p, _ in paras}) or [1]
    preguntas = []
    if conceptos:
        c0 = conceptos[0]
        preguntas = [
            {
                "pregunta": f"¿Qué afirma el libro sobre «{c0['titulo']}»?",
                "tipo": "test",
                "respuesta_clave": c0["explicacion"],
                "opciones": [c0["explicacion"], "Lo contrario.", "Nada.", "Otra cosa."],
                "correcta": 0,
                "paginas": c0["paginas"],
                "motivo": "Es una definición formal.",
            },
            {
                "pregunta": f"Explica {c0['titulo'].lower()}.",
                "tipo": "desarrollo",
                "respuesta_clave": c0["explicacion"],
                "opciones": None,
                "correcta": None,
                "paginas": c0["paginas"],
                "motivo": "El autor lo destaca.",
            },
        ]
    return {
        "conceptos": conceptos,
        "preguntas": preguntas,
        "paja": [f"Ejemplo repetido (p. {pages[0]})"],
    }


def _chapter(analyses: list[dict[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    conceptos = []
    for a in analyses:
        for c in a["conceptos"]:
            if c["titulo"] not in seen:
                seen.add(c["titulo"])
                conceptos.append(c)
    conceptos.sort(key=lambda c: -c["importancia"])
    preguntas = [q for a in analyses for q in a["preguntas"]][:8]
    esquema = [
        {
            "texto": c["titulo"],
            "negrita": c["titulo"].split()[:1],
            "paginas": c["paginas"],
            "hijos": [
                {"texto": c["explicacion"], "negrita": [], "paginas": c["paginas"], "hijos": []}
            ],
        }
        for c in conceptos[:6]
    ]
    imprescindibles = sum(1 for c in conceptos if c["importancia"] == 3)  # noqa: PLR2004
    return {
        "prioridad": "alta" if imprescindibles >= 3 else "media",  # noqa: PLR2004
        "resumen": " ".join(c["explicacion"] for c in conceptos[:3]) or "Capítulo sin contenido.",
        "esquema": esquema,
        "conceptos": conceptos,
        "preguntas": preguntas,
        "paja": sorted({p for a in analyses for p in a["paja"]})[:8],
    }


def _words(text: str) -> set[str]:
    return {w.casefold() for w in _WORD.findall(text)}


def _exams(content: list[str]) -> dict[str, Any]:
    """Sitúa cada pregunta numerada en el capítulo con más palabras en común (o en ninguno).

    ``content[1]`` es la lista de capítulos; los exámenes vienen después. Las imágenes
    no se leen: la IA simulada no ve.
    """
    chapters = [
        (int(m[1]), _words(m[2]), m[2].split(" (pp.")[0])
        for line in content[1].splitlines()
        if (m := _CHAPTER_LINE.match(line))
    ]
    preguntas = []
    for block in content[2:]:
        for line in block.splitlines():
            if not (q := _QUESTION.match(line.strip())):
                continue
            words = _words(q[1])
            number, common, title = max(chapters, key=lambda c: len(c[1] & words))
            hit = len(common & words) >= 1
            preguntas.append(
                {
                    "pregunta": q[1],
                    "tema": " ".join(q[1].split()[:5]).rstrip(",.;:?") if hit else title,
                    "capitulo": number if hit else None,
                }
            )
    return {"preguntas": preguntas}


def _book(chapters: list[dict[str, Any]]) -> dict[str, Any]:
    titles = [c["titulo"] for c in chapters]
    return {
        "mapa": "El libro recorre " + ", ".join(titles) + ".",
        "conexiones": [f"{a} → {b}: se apoya en lo anterior" for a, b in pairwise(titles)],
    }
