"""Cliente de Claude: prompts versionados, salida JSON validada, reintentos y coste.

La respuesta se pide con salidas estructuradas (``output_config.format``) y se valida
con Pydantic. Si no cumple, se repite una vez con el error incluido; si vuelve a
fallar, se lanza ``LLMCallError`` y el fragmento queda marcado como fallido (RNF-05).
"""

import base64
import dataclasses
import json
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib import resources
from string import Template
from typing import Any, Protocol

import anthropic
from pydantic import BaseModel, ValidationError

from criba.core.cost import DEFAULT_MODEL, PRICES, Usage
from criba.core.errors import Cancelled, CribaError, ErrorKind

log = logging.getLogger(__name__)

BACKOFF_SECONDS = (1, 2, 4, 8, 16)
RETRYABLE_STATUS = {429, 500, 529}
FATAL_STATUS = {404}  # p. ej. modelo inexistente: fallaría igual en todos los fragmentos
MAX_OUTPUT_TOKENS = 128_000
DEFAULT_EFFORT = "medium"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
# Modelos que admiten el reintento automático en otro modelo si el primero se niega.
FALLBACK_MODELS = {"claude-sonnet-5-5", "claude-opus-5-5"}
_PROMPT_FILE = re.compile(r"^(?P<name>[a-z_]+)\.v(?P<version>\d+)\.md$")


# --- Prompts ------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Prompt:
    """Plantilla de prompt versionada (``core/prompts/<nombre>.v<N>.md``)."""

    name: str
    version: int
    template: str

    @property
    def id(self) -> str:
        """Identificador para la clave de caché, p. ej. ``analyze_chunk.v1``."""
        return f"{self.name}.v{self.version}"

    def render(self, **values: str) -> str:
        """Sustituye ``${variable}``. Falla si falta alguna."""
        return Template(self.template).substitute(values)


def load_prompt(name: str) -> Prompt:
    """Carga la versión más alta del prompt ``name``."""
    folder = resources.files("criba.core") / "prompts"
    best: tuple[int, str] | None = None
    for entry in folder.iterdir():
        m = _PROMPT_FILE.match(entry.name)
        if m and m["name"] == name:
            version = int(m["version"])
            if best is None or version > best[0]:
                best = (version, entry.read_text(encoding="utf-8"))
    if best is None:
        raise FileNotFoundError(f"No existe el prompt {name}")
    return Prompt(name=name, version=best[0], template=best[1])


# --- Peticiones y respuestas ---------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Image:
    """Imagen para la visión de Claude (OCR)."""

    data: bytes
    media_type: str = "image/jpeg"


Content = list[str | Image]


class Waiter(Protocol):
    """Señal de parada (``threading.Event`` o similar)."""

    def is_set(self) -> bool:
        """Indica si hay que parar."""
        ...

    def wait(self, timeout: float | None = None) -> bool:
        """Espera hasta ``timeout`` segundos; ``True`` si hay que parar."""
        ...


@dataclass(frozen=True, slots=True)
class LLMRequest:
    """Una llamada a la IA con salida estructurada."""

    system: str
    content: Content
    schema: type[BaseModel]
    max_tokens: int = 32_000
    context: dict[str, Any] = field(default_factory=dict)  # contexto de validación
    retry: tuple[str, str] | None = None  # (respuesta anterior, error) para corregir
    stop: Waiter | None = field(default=None, compare=False)  # cancelar sin esperar


@dataclass(frozen=True, slots=True)
class RawResponse:
    """Respuesta sin validar."""

    text: str
    usage: Usage
    model: str
    stop_reason: str | None


class LLMClient(Protocol):
    """Lo que el pipeline necesita de un cliente de IA (real o simulado)."""

    model: str

    def complete(self, request: LLMRequest) -> RawResponse:
        """Hace la llamada. Lanza ``CribaError`` en errores que detienen el proceso."""
        ...


class LLMCallError(Exception):
    """La llamada no dio un resultado válido. El fragmento se reintenta al final."""

    def __init__(self, message: str, usage: Usage | None = None) -> None:
        super().__init__(message)
        self.usage = usage or Usage()


@dataclass(slots=True)
class Result[M: BaseModel]:
    """Resultado validado con los tokens consumidos (incluido el reintento)."""

    value: M
    usage: Usage
    model: str


def _errors_for_model(exc: ValidationError) -> str:
    lines = []
    for err in exc.errors()[:20]:
        where = ".".join(str(p) for p in err["loc"]) or "(raíz)"
        lines.append(f"- {where}: {err['msg']}")
    return "\n".join(lines)


def structured_call[T: BaseModel](
    client: LLMClient, request: LLMRequest, schema: type[T]
) -> Result[T]:
    """Llama, valida y, si la respuesta no sirve, reintenta una vez.

    - Respuesta cortada por ``max_tokens``: se repite con más margen.
    - Respuesta vacía: se repite la misma petición.
    - JSON que no cumple el esquema: se repite incluyendo el error para que lo corrija.

    Los tokens de todos los intentos se cuentan, también si al final falla.
    """
    usage = Usage()
    current = request
    for attempt in (1, 2):
        try:
            raw = client.complete(current)
        except LLMCallError as exc:
            exc.usage += usage
            raise
        except CribaError as exc:
            exc.usage = usage
            raise
        usage += raw.usage
        if raw.stop_reason == "refusal":
            raise LLMCallError("la IA ha rechazado la petición", usage)
        if raw.stop_reason == "max_tokens":
            problem = "respuesta cortada por max_tokens"
            bigger = min(MAX_OUTPUT_TOKENS, round(current.max_tokens * 1.5))
            current = dataclasses.replace(request, max_tokens=bigger, retry=None)
        elif not raw.text.strip():
            problem = "respuesta vacía"
            current = dataclasses.replace(request, retry=None)
        else:
            try:
                value = schema.model_validate_json(raw.text, context=request.context)
            except ValidationError as exc:
                problem = f"respuesta no válida: {exc}"
                current = dataclasses.replace(request, retry=(raw.text, _errors_for_model(exc)))
            else:
                return Result(value=value, usage=usage, model=raw.model)
        log.warning("Intento %d sin resultado: %s", attempt, problem[:200])
    raise LLMCallError(f"sin resultado válido tras reintentar ({problem[:200]})", usage)


# --- Cliente real de Anthropic ---------------------------------------------------------

Sleep = Callable[[float], None]


def _is_billing(exc: anthropic.APIStatusError) -> bool:
    body = exc.body if isinstance(exc.body, dict) else {}
    error = body.get("error") if isinstance(body.get("error"), dict) else {}
    message = f"{exc.message} {error.get('message', '') if isinstance(error, dict) else ''}"
    return (
        exc.status_code == 402  # noqa: PLR2004
        or (isinstance(error, dict) and error.get("type") == "billing_error")
        or "credit balance" in message.lower()
    )


def _content_blocks(content: Content) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for item in content:
        if isinstance(item, Image):
            blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": item.media_type,
                        "data": base64.standard_b64encode(item.data).decode("ascii"),
                    },
                }
            )
        else:
            blocks.append({"type": "text", "text": item})
    return blocks


class AnthropicClient:
    """Cliente de la API de Anthropic con los reintentos y el registro del spec."""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        *,
        effort: str = DEFAULT_EFFORT,
        sleep: Sleep = time.sleep,
        sdk: anthropic.Anthropic | None = None,
    ) -> None:
        if model not in PRICES:
            raise ValueError(f"Modelo no soportado: {model}")
        self.model = model
        self.effort = effort
        self._sleep = sleep
        # Los reintentos los gestionamos aquí (1, 2, 4, 8 y 16 s), no el SDK.
        self._sdk = sdk or anthropic.Anthropic(api_key=api_key, max_retries=0)

    def _params(self, request: LLMRequest) -> dict[str, Any]:
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": _content_blocks(request.content)}
        ]
        if request.retry:
            previous, errors = request.retry
            messages += [
                {"role": "assistant", "content": previous},
                {
                    "role": "user",
                    "content": "Tu respuesta no cumple el esquema por estos motivos:\n"
                    f"{errors}\n\nDevuelve el JSON completo corregido.",
                },
            ]
        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": request.max_tokens,
            # Las instrucciones del sistema son iguales en todas las llamadas del
            # libro: se guardan en la caché de prompts para abaratarlas.
            "system": [
                {"type": "text", "text": request.system, "cache_control": {"type": "ephemeral"}}
            ],
            "messages": messages,
            "output_config": {
                "effort": self.effort,
                "format": {
                    "type": "json_schema",
                    "schema": anthropic.transform_schema(request.schema),
                },
            },
        }
        if self.model in FALLBACK_MODELS:
            params["betas"] = [FALLBACK_BETA]
            params["fallbacks"] = "default"
        return params

    def _once(self, request: LLMRequest) -> RawResponse:
        with self._sdk.beta.messages.stream(**self._params(request)) as stream:
            # Se lee el flujo para poder cancelar a mitad de respuesta (RF-12).
            for _event in stream:
                if request.stop is not None and request.stop.is_set():
                    raise Cancelled
            if request.stop is not None and request.stop.is_set():
                raise Cancelled
            message = stream.get_final_message()
        text = "".join(b.text for b in message.content if b.type == "text")
        u = message.usage
        usage = Usage(
            input=u.input_tokens,
            output=u.output_tokens,
            cache_write=u.cache_creation_input_tokens or 0,
            cache_read=u.cache_read_input_tokens or 0,
        )
        log.info(
            "Llamada %s: entrada=%d salida=%d caché(esc=%d, lec=%d) fin=%s id=%s",
            message.model,
            usage.input,
            usage.output,
            usage.cache_write,
            usage.cache_read,
            message.stop_reason,
            getattr(message, "_request_id", None),
        )
        return RawResponse(
            text=text, usage=usage, model=str(message.model), stop_reason=message.stop_reason
        )

    def complete(self, request: LLMRequest) -> RawResponse:
        """Llama a la API con reintentos ante 429, 500, 529 y errores de red."""
        last: Exception | None = None
        for delay in (*BACKOFF_SECONDS, None):
            try:
                return self._once(request)
            except anthropic.AuthenticationError as exc:
                raise CribaError(ErrorKind.INVALID_KEY, detail=repr(exc)) from exc
            except anthropic.PermissionDeniedError as exc:
                raise CribaError(ErrorKind.INVALID_KEY, detail=repr(exc)) from exc
            except anthropic.APIConnectionError as exc:  # incluye los timeouts
                last = exc
                kind = ErrorKind.OFFLINE
            except anthropic.APIStatusError as exc:
                if _is_billing(exc):
                    raise CribaError(ErrorKind.NO_CREDIT, detail=repr(exc)) from exc
                if exc.status_code in FATAL_STATUS:
                    raise CribaError(ErrorKind.SERVICE_ERROR, detail=repr(exc)) from exc
                if exc.status_code not in RETRYABLE_STATUS:
                    raise LLMCallError(f"error {exc.status_code}: {exc.message}") from exc
                last = exc
                kind = ErrorKind.RATE_LIMITED
            if delay is None:
                break
            log.warning("Reintento en %d s tras %r", delay, last)
            if request.stop is not None:
                if request.stop.wait(delay):
                    raise Cancelled
            else:
                self._sleep(delay)
        raise CribaError(kind, detail=repr(last))


def check_api_key(api_key: str, model: str = DEFAULT_MODEL) -> None:
    """Comprueba la clave sin gastar (consulta el modelo). Lanza ``CribaError``."""
    sdk = anthropic.Anthropic(api_key=api_key, max_retries=2)
    try:
        sdk.models.retrieve(model)
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
        raise CribaError(ErrorKind.INVALID_KEY, detail=repr(exc)) from exc
    except anthropic.APIConnectionError as exc:
        raise CribaError(ErrorKind.OFFLINE, detail=repr(exc)) from exc
    except anthropic.APIStatusError as exc:
        if _is_billing(exc):
            raise CribaError(ErrorKind.NO_CREDIT, detail=repr(exc)) from exc
        raise CribaError(ErrorKind.RATE_LIMITED, detail=repr(exc)) from exc


def dumps(obj: object) -> str:
    """JSON compacto y estable para enviar datos a la IA."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
