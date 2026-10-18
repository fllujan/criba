"""Pipeline completo con la IA simulada (spec §9: «todo el pipeline sin gastar»)."""

import json
import logging
from pathlib import Path

import pytest

from criba import logs
from criba.core import pipeline, schemas
from criba.core.cache import Cache
from criba.core.errors import Cancelled, CribaError, ErrorKind
from criba.core.fake_llm import FakeLLMClient
from criba.core.llm import LLMCallError
from criba.core.pipeline import CancelToken, Options, Stage

MODEL = "claude-sonnet-5-5"


@pytest.fixture
def cache(tmp_path: Path):
    with Cache(tmp_path / "cache.sqlite3") as c:
        yield c


def _opts(tmp_path: Path, **kw) -> Options:
    return Options(asignatura="Biología", output_dir=tmp_path / "out", **kw)


def _run(fx_pdf, tmp_path, cache, llm=None, **kw):
    opts = _opts(tmp_path, **kw)
    prep = pipeline.prepare(fx_pdf, opts, cache, MODEL)
    llm = llm or FakeLLMClient(model=MODEL)
    return pipeline.run(prep, opts, llm, cache), llm, prep


def test_end_to_end_generates_valid_json(fx, tmp_path, cache) -> None:
    result, llm, _ = _run(fx.con_indice, tmp_path, cache)
    assert result.json_path.name == "Biología - datos.json"
    libro = schemas.Libro.model_validate_json(result.json_path.read_text(encoding="utf-8"))
    assert [c.titulo for c in libro.capitulos] == [
        "Capítulo 1. La célula",
        "Capítulo 2. Genética",
        "Capítulo 3. Evolución",
    ]  # la portada (Preliminares) no gasta llamadas
    assert libro.mapa and libro.conexiones
    assert libro.idioma == "es" and libro.modelo == MODEL
    assert libro.paginas_no_procesadas == []
    assert result.calls == 3 + 3 + 1 and result.cached_calls == 0
    assert len(llm.calls_for(schemas.ChunkAnalysis)) == 3


def test_every_idea_cites_pages_inside_its_chapter(fx, tmp_path, cache) -> None:
    """RF-15: cada idea lleva páginas del libro, dentro de su capítulo."""
    result, _, _ = _run(fx.con_indice, tmp_path, cache)
    for cap in result.libro.capitulos:
        a, b = cap.paginas
        items = [*cap.conceptos, *cap.preguntas]
        assert items
        for item in items:
            assert item.paginas and all(a <= p <= b for p in item.paginas)


def test_repeat_makes_no_new_calls(fx, tmp_path, cache) -> None:
    """F2 «hecho cuando»: repetirlo no hace llamadas nuevas (CU4)."""
    _run(fx.con_indice, tmp_path, cache)
    second, llm2, prep2 = _run(fx.con_indice, tmp_path, cache)
    assert llm2.calls == []
    assert second.cached_calls == second.calls
    assert second.cost_usd == 0
    assert prep2.estimate.usd == 0  # la confirmación ya muestra 0 €


def test_estimate_close_to_fake_usage_and_counts_calls(fx, tmp_path, cache) -> None:
    opts = _opts(tmp_path)
    prep = pipeline.prepare(fx.con_indice, opts, cache, MODEL)
    assert prep.estimate.calls == 7
    assert prep.estimate.usd > 0 and prep.estimate.eur < prep.estimate.usd


def test_changing_level_is_a_different_cache_entry(fx, tmp_path, cache) -> None:
    _run(fx.con_indice, tmp_path, cache, nivel="normal")
    _, llm, _ = _run(fx.con_indice, tmp_path, cache, nivel="completo")
    assert len(llm.calls_for(schemas.ChunkAnalysis)) == 3


def test_renaming_subject_reuses_cache(fx, tmp_path, cache) -> None:
    _run(fx.con_indice, tmp_path, cache)
    opts = Options(asignatura="Bio I", output_dir=tmp_path / "out")
    prep = pipeline.prepare(fx.con_indice, opts, cache, MODEL)
    llm = FakeLLMClient(model=MODEL)
    pipeline.run(prep, opts, llm, cache)
    assert llm.calls == []


def test_cancel_then_resume_does_not_repeat_paid_calls(fx, tmp_path, cache) -> None:
    """RF-12 y criterio de aceptación: cancelar y reanudar no repite llamadas pagadas."""
    cancel = CancelToken()
    paid: list = []

    def fail(req):
        if req.schema is schemas.ChunkAnalysis:
            paid.append(req)
            if len(paid) == 2:
                cancel.cancel()

    opts = _opts(tmp_path)
    prep = pipeline.prepare(fx.largo, opts, cache, MODEL)
    llm1 = FakeLLMClient(model=MODEL, fail=fail)
    with pytest.raises(Cancelled):
        pipeline.run(prep, opts, llm1, cache, cancel=cancel)
    total = sum(len(pipeline.chapter_chunks(prep.book, ch)) for ch in prep.selected)
    done_first = {c.content[1] for c in llm1.calls_for(schemas.ChunkAnalysis)}
    assert 2 <= len(done_first) < total
    assert cache.interrupted_jobs()

    prep2 = pipeline.prepare(fx.largo, opts, cache, MODEL)
    assert prep2.estimate.cached_calls == len(done_first)
    llm2 = FakeLLMClient(model=MODEL)
    result = pipeline.run(prep2, opts, llm2, cache)
    second = {c.content[1] for c in llm2.calls_for(schemas.ChunkAnalysis)}
    assert done_first.isdisjoint(second)
    assert len(done_first) + len(second) == total
    assert len(result.libro.capitulos) == 25
    assert cache.interrupted_jobs() == []


def test_failed_chunk_does_not_stop_and_is_retried_at_end(fx, tmp_path, cache) -> None:
    """RNF-05: se reintenta al final; si sigue fallando, se anotan las páginas."""
    attempts: dict[str, int] = {}

    def fail(req):
        if req.schema is schemas.ChunkAnalysis and "Capítulo 2. Genética" in req.content[1]:
            attempts["n"] = attempts.get("n", 0) + 1
            return LLMCallError("simulado")
        return None

    result, _, _ = _run(fx.con_indice, tmp_path, cache, llm=FakeLLMClient(model=MODEL, fail=fail))
    assert attempts["n"] == 2  # intento normal + reintento al final
    assert result.libro.paginas_no_procesadas == [(10, 17)]
    assert [c.titulo for c in result.libro.capitulos] == [
        "Capítulo 1. La célula",
        "Capítulo 3. Evolución",
    ]


def test_chunk_that_recovers_on_final_retry(fx, tmp_path, cache) -> None:
    seen: set[str] = set()

    def fail_once(req):
        if req.schema is schemas.ChunkAnalysis and "Genética" in req.content[1] and not seen:
            seen.add("g")
            return LLMCallError("una vez")
        return None

    result, _, _ = _run(
        fx.con_indice, tmp_path, cache, llm=FakeLLMClient(model=MODEL, fail=fail_once)
    )
    assert result.libro.paginas_no_procesadas == []
    assert len(result.libro.capitulos) == 3


def test_chapter_synthesis_failure_falls_back_to_local_merge(fx, tmp_path, cache) -> None:
    def fail(req):
        return LLMCallError("x") if req.schema is schemas.SintesisCapitulo else None

    result, _, _ = _run(fx.con_indice, tmp_path, cache, llm=FakeLLMClient(model=MODEL, fail=fail))
    assert len(result.libro.capitulos) == 3
    assert all(c.conceptos for c in result.libro.capitulos)


def test_book_synthesis_failure_uses_chapter_summaries(fx, tmp_path, cache) -> None:
    def fail(req):
        return LLMCallError("x") if req.schema is schemas.SintesisLibro else None

    result, _, _ = _run(fx.con_indice, tmp_path, cache, llm=FakeLLMClient(model=MODEL, fail=fail))
    assert "Capítulo 1. La célula" in result.libro.mapa


def test_fatal_error_aborts_and_marks_job_failed(fx, tmp_path, cache) -> None:
    def fail(req):
        return CribaError(ErrorKind.INVALID_KEY)

    with pytest.raises(CribaError) as exc:
        _run(fx.con_indice, tmp_path, cache, llm=FakeLLMClient(model=MODEL, fail=fail))
    assert exc.value.kind is ErrorKind.INVALID_KEY
    assert cache.jobs()[0].status == "failed"


def test_scanned_book_goes_through_ocr(fx, tmp_path, cache) -> None:
    """Criterio de aceptación: lo escaneado se lee y aparece en el resumen."""
    opts = _opts(tmp_path)
    prep = pipeline.prepare(fx.escaneado, opts, cache, MODEL)
    assert prep.ocr_pending == [[1, 2, 3, 4, 5]]
    assert prep.estimate.calls >= 4
    llm = FakeLLMClient(model=MODEL)
    result = pipeline.run(prep, opts, llm, cache)
    assert len(llm.calls_for(schemas.OcrResultado)) == 1
    assert result.libro.paginas_ocr == [1, 2, 3, 4, 5]
    text = json.dumps(result.libro.model_dump(), ensure_ascii=False)
    assert "membrana plasmática" in text
    # Repetir: el OCR también sale de la caché.
    prep2 = pipeline.prepare(fx.escaneado, opts, cache, MODEL)
    assert prep2.ocr_pending == [] and prep2.estimate.usd == 0


def test_chapter_selection_and_page_range(fx, tmp_path, cache) -> None:
    """CU3 / RF-05."""
    result, _, _ = _run(fx.con_indice, tmp_path, cache, chapters=(1, 3))
    assert [c.titulo for c in result.libro.capitulos] == [
        "Capítulo 1. La célula",
        "Capítulo 3. Evolución",
    ]
    result2, _, _ = _run(fx.con_indice, tmp_path, cache, page_range=(5, 12))
    assert [c.paginas for c in result2.libro.capitulos] == [(5, 9), (10, 12)]


def test_progress_events(fx, tmp_path, cache) -> None:
    events: list[pipeline.Progress] = []
    opts = _opts(tmp_path)
    prep = pipeline.prepare(fx.con_indice, opts, cache, MODEL, on_progress=events.append)
    assert events[-1].stage is Stage.READING and events[-1].fraction == 1
    pipeline.run(prep, opts, FakeLLMClient(model=MODEL), cache, on_progress=events.append)
    stages = [e.stage for e in events]
    assert (
        stages.index(Stage.ANALYZING) < stages.index(Stage.SYNTHESIZING) < stages.index(Stage.DONE)
    )
    analyzing = [e for e in events if e.stage is Stage.ANALYZING and e.done]
    assert sorted(e.done for e in analyzing) == [1, 2, 3]
    assert all(e.chapters == 4 for e in analyzing)
    assert events[-1].stage is Stage.DONE
    costs = [e.cost_usd for e in events]
    assert costs[-1] > 0


def test_language_option_overrides_detection(fx, tmp_path, cache) -> None:
    result, llm, _ = _run(fx.con_indice, tmp_path, cache, idioma="en")
    assert result.libro.idioma == "en"
    assert "Escribe en inglés." in llm.calls[0].system


def test_model_mismatch_rejected(fx, tmp_path, cache) -> None:
    opts = _opts(tmp_path)
    prep = pipeline.prepare(fx.con_indice, opts, cache, MODEL)
    with pytest.raises(ValueError, match="modelo"):
        pipeline.run(prep, opts, FakeLLMClient(model="claude-haiku-5-5"), cache)


def test_cannot_write_output(fx, tmp_path, cache) -> None:
    blocker = tmp_path / "out"
    blocker.write_text("soy un archivo, no una carpeta")
    with pytest.raises(CribaError) as exc:
        _run(fx.con_indice, tmp_path, cache)
    assert exc.value.kind in {ErrorKind.CANNOT_WRITE, ErrorKind.DISK_FULL}


def test_safe_filename() -> None:
    assert pipeline.safe_filename('Física: "ondas"/óptica?') == "Física ondas óptica"
    assert pipeline.safe_filename("...") == "Criba"


def test_api_key_never_written_to_disk(fx, tmp_path, cache, app_dirs, monkeypatch) -> None:
    """Criterio de aceptación: la clave no aparece en ningún archivo ni en los logs."""
    key = "sk-ant-api03-" + "Z" * 48
    monkeypatch.setenv("ANTHROPIC_API_KEY", key)
    logs.setup(logging.DEBUG)
    try:

        def fail(req):
            logging.getLogger("criba.core.llm").error("error con %s", key)

        _run(fx.con_indice, tmp_path, cache, llm=FakeLLMClient(model=MODEL, fail=fail))
    finally:
        logs.shutdown()
    for path in [*tmp_path.rglob("*"), *app_dirs.rglob("*")]:
        if path.is_file():
            assert key.encode() not in path.read_bytes(), path
