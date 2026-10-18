"""Cliente de IA: validación con reintento, reintentos de red y errores del spec §8.

El SDK real se sustituye por un doble que imita ``client.beta.messages.stream``.
"""

import json
from contextlib import contextmanager
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from criba.core import llm, schemas
from criba.core.errors import CribaError, ErrorKind
from criba.core.fake_llm import FakeLLMClient
from criba.core.llm import AnthropicClient, LLMCallError, LLMRequest, structured_call

VALID = json.dumps({"mapa": "Un libro.", "conexiones": ["A → B: base"]})
REQ = LLMRequest(system="sistema", content=["hola"], schema=schemas.SintesisLibro)
_REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def _status(cls, code, body=None):
    return cls("fallo", response=httpx2.Response(code, request=_REQUEST), body=body)


class FakeSDK:
    """Imita ``anthropic.Anthropic`` lo justo para el cliente."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)  # str (texto) o excepción
        self.params: list[dict] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    @contextmanager
    def _stream(self, **params):
        self.params.append(params)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        stop = "end_turn"
        if isinstance(outcome, tuple):
            outcome, stop = outcome
        msg = SimpleNamespace(
            content=[
                SimpleNamespace(type="thinking", thinking=""),
                SimpleNamespace(type="text", text=outcome),
            ],
            usage=SimpleNamespace(
                input_tokens=100,
                output_tokens=50,
                cache_creation_input_tokens=10,
                cache_read_input_tokens=5,
            ),
            model=params["model"],
            stop_reason=stop,
        )
        yield SimpleNamespace(get_final_message=lambda: msg)


def _client(outcomes, model="claude-sonnet-5-5"):
    sleeps: list[float] = []
    sdk = FakeSDK(outcomes)
    return AnthropicClient("sk-ant-test", model, sleep=sleeps.append, sdk=sdk), sdk, sleeps


# --- Prompts ------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["analyze_chunk", "synthesize_chapter", "synthesize_book", "ocr"])
def test_prompts_load_with_version(name) -> None:
    p = llm.load_prompt(name)
    assert p.version >= 1 and p.id == f"{name}.v{p.version}"


def test_prompt_render_requires_all_values() -> None:
    p = llm.load_prompt("analyze_chunk")
    with pytest.raises(KeyError):
        p.render(asignatura="Bio")


def test_prompts_follow_spec_rules() -> None:
    text = llm.load_prompt("analyze_chunk").template
    assert (
        "Eres un profesor experto que prepara a un alumno para el examen de ${asignatura}" in text
    )
    for rule in ("prohibido añadir conocimiento", "[p. N]", "40 palabras", "motivo", "paja"):
        assert rule in text


def test_unknown_prompt() -> None:
    with pytest.raises(FileNotFoundError):
        llm.load_prompt("no_existe")


# --- Validación con reintento ---------------------------------------------------------------


def test_structured_call_valid_first_time() -> None:
    client, sdk, _ = _client([VALID])
    result = structured_call(client, REQ, schemas.SintesisLibro)
    assert result.value.mapa == "Un libro."
    assert result.usage.input == 100 and result.usage.cache_read == 5
    assert len(sdk.params) == 1


def test_invalid_json_retried_once_with_error_included() -> None:
    client, sdk, _ = _client(['{"mapa": 3}', VALID])
    result = structured_call(client, REQ, schemas.SintesisLibro)
    assert result.value.conexiones == ["A → B: base"]
    assert result.usage.input == 200  # se suman las dos llamadas
    retry_msgs = sdk.params[1]["messages"]
    assert [m["role"] for m in retry_msgs] == ["user", "assistant", "user"]
    assert "no cumple el esquema" in retry_msgs[2]["content"]
    assert "mapa" in retry_msgs[2]["content"]


def test_invalid_twice_fails_chunk() -> None:
    client, _, _ = _client(["no json", "{}"])
    with pytest.raises(LLMCallError):
        structured_call(client, REQ, schemas.SintesisLibro)


def test_refusal_fails_without_retry() -> None:
    client, sdk, _ = _client([("{}", "refusal")])
    with pytest.raises(LLMCallError):
        structured_call(client, REQ, schemas.SintesisLibro)
    assert len(sdk.params) == 1


def test_fake_invalid_first_exercises_retry() -> None:
    fake = FakeLLMClient(invalid_first=True)
    req = LLMRequest(system="s", content=["Capítulos (JSON):", "[]"], schema=schemas.SintesisLibro)
    structured_call(fake, req, schemas.SintesisLibro)
    assert len(fake.calls) == 2 and fake.calls[1].retry is not None


# --- Parámetros de la petición ----------------------------------------------------------------


def test_request_params_structured_output_cache_and_fallbacks() -> None:
    client, sdk, _ = _client([VALID])
    client.complete(REQ)
    p = sdk.params[0]
    assert p["model"] == "claude-sonnet-5-5"
    assert p["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert p["output_config"]["format"]["type"] == "json_schema"
    assert p["output_config"]["effort"] == "medium"
    assert "tool_choice" not in p  # forzar herramienta da 400 en los modelos 5.5
    assert "thinking" not in p
    assert p["fallbacks"] == "default" and p["betas"] == [llm.FALLBACK_BETA]


def test_haiku_has_no_fallbacks() -> None:
    client, sdk, _ = _client([VALID], model="claude-haiku-5-5")
    client.complete(REQ)
    assert "fallbacks" not in sdk.params[0]


def test_images_sent_as_base64() -> None:
    client, sdk, _ = _client([VALID])
    req = LLMRequest(
        system="s", content=["Página 1:", llm.Image(b"\xff\xd8jpeg")], schema=schemas.SintesisLibro
    )
    client.complete(req)
    blocks = sdk.params[0]["messages"][0]["content"]
    assert blocks[1]["type"] == "image"
    assert blocks[1]["source"]["media_type"] == "image/jpeg"


def test_unknown_model_rejected() -> None:
    with pytest.raises(ValueError, match="no soportado"):
        AnthropicClient("k", "gpt-4", sdk=FakeSDK([]))


# --- Reintentos y errores (§6 Llamadas a la API, §8) -------------------------------------------


@pytest.mark.parametrize("code", [429, 500, 529])
def test_retryable_status_backoff(code) -> None:
    exc_cls = anthropic.RateLimitError if code == 429 else anthropic.InternalServerError
    client, _, sleeps = _client([_status(exc_cls, code), _status(exc_cls, code), VALID])
    assert client.complete(REQ).text == VALID
    assert sleeps == [1, 2]


def test_persistent_rate_limit_after_1_2_4_8_16() -> None:
    client, sdk, sleeps = _client([_status(anthropic.RateLimitError, 429)] * 6)
    with pytest.raises(CribaError) as exc:
        client.complete(REQ)
    assert exc.value.kind is ErrorKind.RATE_LIMITED
    assert sleeps == [1, 2, 4, 8, 16]
    assert len(sdk.params) == 6


def test_offline_after_retries() -> None:
    client, _, sleeps = _client([anthropic.APIConnectionError(request=_REQUEST)] * 6)
    with pytest.raises(CribaError) as exc:
        client.complete(REQ)
    assert exc.value.kind is ErrorKind.OFFLINE and len(sleeps) == 5


def test_network_recovers() -> None:
    client, _, _ = _client([anthropic.APIConnectionError(request=_REQUEST), VALID])
    assert client.complete(REQ).text == VALID


def test_invalid_key_not_retried() -> None:
    client, sdk, sleeps = _client([_status(anthropic.AuthenticationError, 401)])
    with pytest.raises(CribaError) as exc:
        client.complete(REQ)
    assert exc.value.kind is ErrorKind.INVALID_KEY
    assert sleeps == [] and len(sdk.params) == 1


@pytest.mark.parametrize(
    ("code", "body"),
    [(400, {"type": "error", "error": {"type": "billing_error", "message": "x"}}), (402, None)],
)
def test_no_credit(code, body) -> None:
    exc_cls = anthropic.BadRequestError if code == 400 else anthropic.APIStatusError
    client, _, _ = _client([_status(exc_cls, code, body)])
    with pytest.raises(CribaError) as exc:
        client.complete(REQ)
    assert exc.value.kind is ErrorKind.NO_CREDIT


def test_other_400_fails_only_the_chunk() -> None:
    client, _, sleeps = _client([_status(anthropic.BadRequestError, 400, {"error": {"type": "x"}})])
    with pytest.raises(LLMCallError):
        client.complete(REQ)
    assert sleeps == []


def test_check_api_key_maps_errors(monkeypatch) -> None:
    class SDK:
        def __init__(self, **_):
            self.models = SimpleNamespace(retrieve=self.retrieve)

        def retrieve(self, model):
            raise _status(anthropic.AuthenticationError, 401)

    monkeypatch.setattr(anthropic, "Anthropic", SDK)
    with pytest.raises(CribaError) as exc:
        llm.check_api_key("sk-ant-mala")
    assert exc.value.kind is ErrorKind.INVALID_KEY


def test_check_api_key_ok(monkeypatch) -> None:
    calls = []

    class SDK:
        def __init__(self, **kw):
            calls.append(kw)
            self.models = SimpleNamespace(retrieve=lambda model: None)

    monkeypatch.setattr(anthropic, "Anthropic", SDK)
    llm.check_api_key("sk-ant-buena")
    assert calls[0]["api_key"] == "sk-ant-buena"
