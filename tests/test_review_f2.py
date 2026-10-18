"""Regresiones encontradas en la revisión de código de la F2."""

import threading
from pathlib import Path

import anthropic
import pymupdf
import pytest

from criba.core import llm as llm_mod
from criba.core import pipeline, schemas
from criba.core.cache import Cache
from criba.core.errors import Cancelled, CribaError, ErrorKind
from criba.core.fake_llm import FakeLLMClient
from criba.core.llm import AnthropicClient, LLMCallError, LLMRequest, structured_call
from criba.core.pipeline import CancelToken, Options
from tests.test_llm import REQ, VALID, FakeSDK, _client, _status

MODEL = "claude-sonnet-5-5"


@pytest.fixture
def cache(tmp_path: Path):
    with Cache(tmp_path / "cache.sqlite3") as c:
        yield c


def _mixed_book(fx, tmp_path: Path) -> Path:
    """Libro con texto y la página 12 escaneada (imagen)."""
    src = pymupdf.open(fx.sin_indice)
    out = pymupdf.open()
    out.insert_pdf(src, to_page=10)
    pix = src[11].get_pixmap(dpi=80)
    page = out.new_page(width=src[11].rect.width, height=src[11].rect.height)
    page.insert_image(page.rect, pixmap=pix)
    out.insert_pdf(src, from_page=12)
    path = tmp_path / "mixto.pdf"
    out.save(path)
    return path


def _run(pdf, tmp_path, cache, llm, **kw):
    opts = Options(asignatura="Bio", output_dir=tmp_path / "out", **kw)
    prep = pipeline.prepare(pdf, opts, cache, MODEL)
    return pipeline.run(prep, opts, llm, cache), prep


# 1. OCR fallido ----------------------------------------------------------------------


def test_failed_ocr_is_retried_and_reported(fx, tmp_path, cache) -> None:
    pdf = _mixed_book(fx, tmp_path)
    llm = FakeLLMClient(
        model=MODEL, fail=lambda r: LLMCallError("x") if r.schema is schemas.OcrResultado else None
    )
    result, prep = _run(pdf, tmp_path, cache, llm)
    assert prep.scanned_pages == [12]
    assert len(llm.calls_for(schemas.OcrResultado)) == 2  # intento + reintento al final
    assert (12, 12) in result.libro.paginas_no_procesadas
    assert result.libro.capitulos


def test_all_ocr_failed_is_not_reported_as_no_text(fx, tmp_path, cache) -> None:
    llm = FakeLLMClient(
        model=MODEL, fail=lambda r: LLMCallError("x") if r.schema is schemas.OcrResultado else None
    )
    with pytest.raises(CribaError) as exc:
        _run(fx.escaneado, tmp_path, cache, llm)
    assert exc.value.kind is ErrorKind.PROCESSING_FAILED


# 2. OCR por página: cambiar el rango no vuelve a pagar --------------------------------


def test_ocr_cached_per_page_across_ranges(fx, tmp_path, cache) -> None:
    llm1 = FakeLLMClient(model=MODEL)
    _run(fx.escaneado, tmp_path, cache, llm1, page_range=(2, 5))
    assert [c.context["paginas_ocr"] for c in llm1.calls_for(schemas.OcrResultado)] == [
        [2, 3, 4, 5]
    ]
    llm2 = FakeLLMClient(model=MODEL)
    _run(fx.escaneado, tmp_path, cache, llm2)
    assert [c.context["paginas_ocr"] for c in llm2.calls_for(schemas.OcrResultado)] == [[1]]


# 3. Errores 4xx ---------------------------------------------------------------------


def test_low_credit_400_message_is_no_credit() -> None:
    body = {
        "type": "error",
        "error": {
            "type": "invalid_request_error",
            "message": "Your credit balance is too low to access the Anthropic API.",
        },
    }
    exc = anthropic.BadRequestError(
        "Your credit balance is too low to access the Anthropic API.",
        response=_status(anthropic.BadRequestError, 400).response,
        body=body,
    )
    client, _, _ = _client([exc])
    with pytest.raises(CribaError) as err:
        client.complete(REQ)
    assert err.value.kind is ErrorKind.NO_CREDIT


def test_404_is_fatal_service_error() -> None:
    client, _, _ = _client([_status(anthropic.NotFoundError, 404)])
    with pytest.raises(CribaError) as err:
        client.complete(REQ)
    assert err.value.kind is ErrorKind.SERVICE_ERROR


def test_all_chunks_failed_is_processing_failed(fx, tmp_path, cache) -> None:
    llm = FakeLLMClient(
        model=MODEL, fail=lambda r: LLMCallError("x") if r.schema is schemas.ChunkAnalysis else None
    )
    with pytest.raises(CribaError) as exc:
        _run(fx.con_indice, tmp_path, cache, llm)
    assert exc.value.kind is ErrorKind.PROCESSING_FAILED


# 4. Tokens de los intentos fallidos ----------------------------------------------------


def test_failed_structured_call_reports_usage() -> None:
    client, _, _ = _client(["no json", "{}"])
    with pytest.raises(LLMCallError) as exc:
        structured_call(client, REQ, schemas.SintesisLibro)
    assert exc.value.usage.input == 200


def test_failed_chunks_cost_is_counted(fx, tmp_path, cache) -> None:
    class AlwaysInvalid(FakeLLMClient):
        def complete(self, request):
            raw = super().complete(request)
            if request.schema is schemas.ChunkAnalysis and "Genética" in request.content[1]:
                return llm_mod.RawResponse("{}", raw.usage, raw.model, "end_turn")
            return raw

    result, _ = _run(fx.con_indice, tmp_path, cache, AlwaysInvalid(model=MODEL))
    genetics = [c for c in result.libro.capitulos if "Genética" in c.titulo]
    assert genetics == []
    chunk_calls = 4 + 2  # 2 capítulos bien + Genética fallida dos veces (y reintento final)
    assert result.usage.input > 0 and result.calls >= chunk_calls - 2


# 5. Reintento con respuesta vacía o cortada ------------------------------------------------


def test_empty_reply_retried_without_assistant_turn() -> None:
    client, sdk, _ = _client(["", VALID])
    structured_call(client, REQ, schemas.SintesisLibro)
    assert [m["role"] for m in sdk.params[1]["messages"]] == ["user"]


def test_max_tokens_reply_retried_with_more_room() -> None:
    client, sdk, _ = _client([('{"mapa": "cort', "max_tokens"), VALID])
    structured_call(client, REQ, schemas.SintesisLibro)
    assert sdk.params[1]["max_tokens"] > sdk.params[0]["max_tokens"]
    assert [m["role"] for m in sdk.params[1]["messages"]] == ["user"]


# 6. El token del usuario no queda cancelado tras un error grave ------------------------------


def test_fatal_error_does_not_cancel_callers_token(fx, tmp_path, cache) -> None:
    token = CancelToken()
    llm = FakeLLMClient(model=MODEL, fail=lambda r: CribaError(ErrorKind.OFFLINE))
    opts = Options(asignatura="Bio", output_dir=tmp_path / "out")
    prep = pipeline.prepare(fx.con_indice, opts, cache, MODEL)
    with pytest.raises(CribaError):
        pipeline.run(prep, opts, llm, cache, cancel=token)
    assert not token.cancelled
    result = pipeline.run(prep, opts, FakeLLMClient(model=MODEL), cache, cancel=token)
    assert result.libro.capitulos  # «Reintentar» con el mismo token funciona


# 7. Cancelar no espera los reintentos ni la respuesta en curso -------------------------------


def test_cancel_interrupts_backoff() -> None:
    stop = threading.Event()
    stop.set()
    client, _, sleeps = _client([_status(anthropic.RateLimitError, 429)] * 6)
    req = LLMRequest(system="s", content=["x"], schema=schemas.SintesisLibro, stop=stop)
    with pytest.raises(Cancelled):
        client.complete(req)
    assert sleeps == []


def test_cancel_interrupts_streaming() -> None:
    stop = threading.Event()

    class StreamingSDK(FakeSDK):
        def _stream(self, **params):
            stop.set()  # el usuario cancela mientras llega la respuesta
            return super()._stream(**params)

    sdk = StreamingSDK([VALID])
    client = AnthropicClient("k", MODEL, sdk=sdk)
    req = LLMRequest(system="s", content=["x"], schema=schemas.SintesisLibro, stop=stop)
    with pytest.raises(Cancelled):
        client.complete(req)


# 8. Límite de uso persistente: se reintenta automáticamente ------------------------------------


def test_persistent_rate_limit_waits_and_retries(fx, tmp_path, cache, monkeypatch) -> None:
    monkeypatch.setattr(pipeline, "RATE_LIMIT_WAIT", 0.0)
    failures = {"n": 0}

    def fail(req):
        if failures["n"] < 2:
            failures["n"] += 1
            return CribaError(ErrorKind.RATE_LIMITED)
        return None

    events: list[pipeline.Progress] = []
    opts = Options(asignatura="Bio", output_dir=tmp_path / "out")
    prep = pipeline.prepare(fx.con_indice, opts, cache, MODEL)
    result = pipeline.run(
        prep, opts, FakeLLMClient(model=MODEL, fail=fail), cache, on_progress=events.append
    )
    assert result.libro.capitulos
    assert any(e.notice == "rate_limited" for e in events)


def test_rate_limit_gives_up_after_rounds(fx, tmp_path, cache, monkeypatch) -> None:
    monkeypatch.setattr(pipeline, "RATE_LIMIT_WAIT", 0.0)
    monkeypatch.setattr(pipeline, "RATE_LIMIT_ROUNDS", 2)
    llm = FakeLLMClient(model=MODEL, fail=lambda r: CribaError(ErrorKind.RATE_LIMITED))
    with pytest.raises(CribaError) as exc:
        _run(fx.con_indice, tmp_path, cache, llm)
    assert exc.value.kind is ErrorKind.RATE_LIMITED


# 9. El OCR solo escribe las páginas pedidas ---------------------------------------------------


def test_ocr_extra_page_ignored(fx, tmp_path, cache) -> None:
    pdf = _mixed_book(fx, tmp_path)

    class ExtraPage(FakeLLMClient):
        def _answer(self, request):
            answer = super()._answer(request)
            if request.schema is schemas.OcrResultado:
                answer["paginas"].append({"pagina": 3, "texto": "TEXTO INTRUSO"})
            return answer

    result, _ = _run(pdf, tmp_path, cache, ExtraPage(model=MODEL))
    assert "TEXTO INTRUSO" not in result.json_path.read_text(encoding="utf-8")
    assert result.libro.paginas_ocr == [12]
