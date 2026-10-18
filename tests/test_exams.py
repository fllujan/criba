"""Exámenes antiguos (RF-09, F5): lectura, petición a la IA e integración en el reduce."""

from pathlib import Path
from typing import Any

import pymupdf
import pytest

from criba.core import analyze, exams, pipeline, schemas
from criba.core.cache import Cache
from criba.core.errors import CribaError, ErrorKind
from criba.core.fake_llm import FakeLLMClient
from criba.core.llm import Image, LLMCallError, LLMRequest
from criba.core.pipeline import Options
from criba.render import render_book

MODEL = "claude-sonnet-5-5"


@pytest.fixture
def cache(tmp_path: Path):
    with Cache(tmp_path / "cache.sqlite3") as c:
        yield c


def _opts(tmp_path: Path, **kw) -> Options:
    return Options(asignatura="Biología", output_dir=tmp_path / "out", **kw)


def _run(pdf, tmp_path, cache, llm=None, **kw):
    opts = _opts(tmp_path, **kw)
    prep = pipeline.prepare(pdf, opts, cache, MODEL)
    llm = llm or FakeLLMClient(model=MODEL)
    return pipeline.run(prep, opts, llm, cache), llm, prep


def _by_title(result) -> dict[str, schemas.Capitulo]:
    return {c.titulo: c for c in result.libro.capitulos}


# --- Lectura (local, gratis) ------------------------------------------------------------


def test_read_exam_with_text(fx) -> None:
    exam = exams.read_exam(fx.examen)
    assert exam.name == "examen.pdf"
    assert exam.pages == 1 and exam.scanned == ()
    assert "[p. 1]" in exam.text
    assert "leyes de Mendel" in exam.text
    assert len(exam.sha256) == 64


def test_read_scanned_exam_keeps_its_pages_for_vision(fx) -> None:
    exam = exams.read_exam(fx.examen_escaneado)
    assert exam.scanned == (1,)
    assert exam.text == ""


@pytest.mark.parametrize(
    ("name", "kind"),
    [
        ("protegido", ErrorKind.PASSWORD_PROTECTED),
        ("danado", ErrorKind.CORRUPT),
        ("largo", ErrorKind.EXAM_TOO_LONG),
    ],
)
def test_read_exam_rejects_bad_files(fx, name, kind) -> None:
    with pytest.raises(CribaError) as err:
        exams.read_exam(getattr(fx, name))
    assert err.value.kind is kind


def test_read_exam_without_text_or_images(tmp_path) -> None:
    path = tmp_path / "vacio.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.save(path)
    with pytest.raises(CribaError) as err:
        exams.read_exam(path)
    assert err.value.kind is ErrorKind.NO_TEXT


# --- Petición ----------------------------------------------------------------------------


def test_request_lists_chapters_and_sends_scanned_pages_as_images(fx, tmp_path, cache) -> None:
    prep = pipeline.prepare(fx.con_indice, _opts(tmp_path), cache, MODEL)
    texto, foto = exams.read_exam(fx.examen), exams.read_exam(fx.examen_escaneado)
    req = exams.exams_request(prep.study, prep.selected, [texto, foto])
    strings = "\n".join(c for c in req.content if isinstance(c, str))
    assert "2. Capítulo 1. La célula (pp. 2–9)" in strings  # 1 es la portada
    assert "Leyes de Mendel" in strings  # los apartados ayudan a situar cada pregunta
    assert "Examen «examen.pdf»" in strings and "leyes de Mendel" in strings
    assert "Examen «examen_escaneado.pdf», página 1" in strings
    assert sum(isinstance(c, Image) for c in req.content) == 1
    assert req.schema is schemas.AnalisisExamenes
    assert req.context == {"capitulos": len(prep.selected)}
    assert "Biología" in req.system


def test_impossible_chapter_number_only_drops_that_question() -> None:
    ok = {"preguntas": [{"pregunta": "¿X?", "tema": "X", "capitulo": None}]}
    schemas.AnalisisExamenes.model_validate(ok, context={"capitulos": 3})
    mixed = {
        "preguntas": [
            {"pregunta": "¿X?", "tema": "X", "capitulo": 4},
            {"pregunta": "¿Y?", "tema": "Y", "capitulo": 2},
        ]
    }
    result = schemas.AnalisisExamenes.model_validate(mixed, context={"capitulos": 3})
    assert [q.capitulo for q in result.preguntas] == [None, 2]


def test_topics_by_chapter_groups_and_dedupes() -> None:
    q = schemas.PreguntaExamen
    result = schemas.AnalisisExamenes(
        preguntas=[
            q(pregunta="¿Mendel?", tema="Leyes de Mendel", capitulo=2),
            q(pregunta="Enuncia Mendel", tema="leyes de mendel", capitulo=2),
            q(pregunta="¿Pitágoras?", tema="Pitágoras", capitulo=None),
            q(pregunta="¿Célula?", tema="Teoría celular", capitulo=1),
        ]
    )
    topics = exams.topics_by_chapter(result)
    assert sorted(topics) == [0, 1]
    assert [t.tema for t in topics[1]] == ["Leyes de Mendel"]
    assert exams.topic_names(topics[1]) == ["Leyes de Mendel"]


def test_raise_priority() -> None:
    assert [analyze.raise_priority(p) for p in ("baja", "media", "alta")] == [
        "media",
        "alta",
        "alta",
    ]


# --- Pipeline ------------------------------------------------------------------------


class _LowPriority(FakeLLMClient):
    """IA simulada que da prioridad baja a todos los capítulos."""

    def _answer(self, request: LLMRequest) -> dict[str, Any]:
        answer = super()._answer(request)
        if request.schema is schemas.SintesisCapitulo:
            answer["prioridad"] = "baja"
        return answer


def test_exam_topics_raise_priority_and_carry_the_label(fx, tmp_path, cache) -> None:
    result, llm, _ = _run(
        fx.con_indice, tmp_path, cache, llm=_LowPriority(model=MODEL), exams=(fx.examen,)
    )
    caps = _by_title(result)
    celula, genetica, evolucion = (
        caps["Capítulo 1. La célula"],
        caps["Capítulo 2. Genética"],
        caps["Capítulo 3. Evolución"],
    )
    assert (genetica.ha_caido_en_examen, evolucion.ha_caido_en_examen) == (True, True)
    assert not celula.ha_caido_en_examen
    assert (genetica.prioridad, evolucion.prioridad, celula.prioridad) == ("media", "media", "baja")
    assert genetica.temas_examen and evolucion.temas_examen and celula.temas_examen == []
    assert len(llm.calls_for(schemas.AnalisisExamenes)) == 1


def test_chapter_request_includes_exam_questions_only_where_they_fell(fx, tmp_path, cache) -> None:
    _, llm, _ = _run(fx.con_indice, tmp_path, cache, exams=(fx.examen,))
    texts = {
        r.content[0].splitlines()[0]: "\n".join(c for c in r.content if isinstance(c, str))
        for r in llm.calls_for(schemas.SintesisCapitulo)
    }
    assert "Ha caído en examen" in texts["Capítulo: Capítulo 2. Genética"]
    assert "leyes de Mendel" in texts["Capítulo: Capítulo 2. Genética"]
    assert "Ha caído en examen" not in texts["Capítulo: Capítulo 1. La célula"]


def test_without_exams_nothing_changes(fx, tmp_path, cache) -> None:
    result, llm, _ = _run(fx.con_indice, tmp_path, cache)
    assert not any(c.ha_caido_en_examen for c in result.libro.capitulos)
    assert llm.calls_for(schemas.AnalisisExamenes) == []


def test_adding_exams_later_only_pays_what_changes(fx, tmp_path, cache) -> None:
    _run(fx.con_indice, tmp_path, cache)
    _, llm, _ = _run(fx.con_indice, tmp_path, cache, exams=(fx.examen,))
    assert llm.calls_for(schemas.ChunkAnalysis) == []  # el map no depende de los exámenes
    assert len(llm.calls_for(schemas.AnalisisExamenes)) == 1
    assert len(llm.calls_for(schemas.SintesisCapitulo)) == 2  # solo Genética y Evolución
    assert len(llm.calls_for(schemas.SintesisLibro)) == 1
    # Y repetir con los mismos exámenes ya no cuesta nada.
    _, again, _ = _run(fx.con_indice, tmp_path, cache, exams=(fx.examen,))
    assert again.calls == []


def test_estimate_counts_the_exam_call_and_cache(fx, tmp_path, cache) -> None:
    plain = pipeline.prepare(fx.con_indice, _opts(tmp_path), cache, MODEL).estimate
    with_exams = pipeline.prepare(
        fx.con_indice, _opts(tmp_path, exams=(fx.examen, fx.examen_escaneado)), cache, MODEL
    ).estimate
    assert with_exams.calls == plain.calls + 1
    assert with_exams.usd > plain.usd
    _run(fx.con_indice, tmp_path, cache, exams=(fx.examen, fx.examen_escaneado))
    after = pipeline.prepare(
        fx.con_indice, _opts(tmp_path, exams=(fx.examen, fx.examen_escaneado)), cache, MODEL
    ).estimate
    assert after.cached_calls == after.calls
    assert after.usd == 0


def test_estimate_with_pending_exams_does_not_count_old_syntheses_as_free(
    fx, tmp_path, cache
) -> None:
    """Hasta analizar los exámenes no se sabe qué capítulos cambian: se estima por lo alto."""
    _run(fx.con_indice, tmp_path, cache)
    est = pipeline.prepare(
        fx.con_indice, _opts(tmp_path, exams=(fx.examen,)), cache, MODEL
    ).estimate
    assert est.calls - est.cached_calls == 1 + 3 + 1  # exámenes, 3 capítulos y libro


def test_failed_exam_analysis_is_retried_then_skipped(fx, tmp_path, cache) -> None:
    def fail(request: LLMRequest) -> Exception | None:
        if request.schema is schemas.AnalisisExamenes:
            return LLMCallError("no cumple")
        return None

    llm = FakeLLMClient(model=MODEL, fail=fail)
    result, _, _ = _run(fx.con_indice, tmp_path, cache, llm=llm, exams=(fx.examen,))
    assert len(llm.calls_for(schemas.AnalisisExamenes)) == 2
    assert not any(c.ha_caido_en_examen for c in result.libro.capitulos)
    assert result.exams_failed


def test_exam_cache_key_depends_on_exams_and_selection(fx, tmp_path, cache) -> None:
    a = pipeline.prepare(fx.con_indice, _opts(tmp_path, exams=(fx.examen,)), cache, MODEL)
    b = pipeline.prepare(fx.con_indice, _opts(tmp_path, exams=(fx.examen_escaneado,)), cache, MODEL)
    c = pipeline.prepare(
        fx.con_indice, _opts(tmp_path, exams=(fx.examen,), chapters=(1, 2)), cache, MODEL
    )
    keys = {pipeline.exams_key(p) for p in (a, b, c)}
    assert len(keys) == 3


def test_replan_reuses_exams_already_read(fx, tmp_path, cache, monkeypatch) -> None:
    prep = pipeline.prepare(fx.con_indice, _opts(tmp_path, exams=(fx.examen,)), cache, MODEL)
    reads: list[Path] = []
    real = exams.read_exam
    monkeypatch.setattr(exams, "read_exam", lambda p: reads.append(p) or real(p))
    again = pipeline.replan(
        prep, _opts(tmp_path, exams=(fx.examen, fx.examen_escaneado), nivel="completo"), cache
    )
    assert reads == [fx.examen_escaneado]
    assert [e.name for e in again.exams] == ["examen.pdf", "examen_escaneado.pdf"]
    none = pipeline.replan(again, _opts(tmp_path), cache)
    assert none.exams == []


def test_options_record_exams(tmp_path) -> None:
    opts = _opts(tmp_path, exams=(tmp_path / "a.pdf",))
    assert opts.as_dict()["exams"] == [str(tmp_path / "a.pdf")]


def test_outline_pdf_shows_label_and_topics(fx, tmp_path, cache) -> None:
    result, _, _ = _run(fx.con_indice, tmp_path, cache, exams=(fx.examen,))
    with pymupdf.open(result.outline_pdf) as doc:
        text = " ".join(page.get_text() for page in doc)
    assert "HA CAÍDO EN EXAMEN" in text
    genetica = _by_title(result)["Capítulo 2. Genética"]
    assert genetica.temas_examen[0] in text


def test_old_json_without_exam_topics_still_loads(fx, tmp_path, cache) -> None:
    result, _, _ = _run(fx.con_indice, tmp_path, cache)
    data = result.libro.model_dump(mode="json")
    for cap in data["capitulos"]:
        del cap["temas_examen"]
    libro = schemas.Libro.model_validate(data)
    render_book(libro, tmp_path / "regenerado")


def test_same_exam_twice_counts_once(fx, tmp_path, cache) -> None:
    copy = tmp_path / "copia.pdf"
    copy.write_bytes(fx.examen.read_bytes())
    prep = pipeline.prepare(
        fx.con_indice, _opts(tmp_path, exams=(fx.examen, fx.examen, copy)), cache, MODEL
    )
    assert [e.name for e in prep.exams] == ["examen.pdf"]


# --- Revisión de código de F5 -----------------------------------------------------------


def _exam(name: str, pages: int, scanned: int = 0) -> exams.Exam:
    return exams.Exam(Path(name), name, name * 8, pages, "[p. 1]\nx", tuple(range(1, scanned + 1)))


def test_limits_keep_everything_in_one_call() -> None:
    assert exams.limits_problem([_exam("a", 30), _exam("b", 30)]) is None
    assert exams.limits_problem([_exam("a", 40), _exam("b", 21)]) is ErrorKind.EXAMS_TOO_BIG
    assert exams.limits_problem([_exam("a", 21, scanned=21)]) is ErrorKind.EXAMS_TOO_BIG
    assert exams.limits_problem([_exam(str(i), 1) for i in range(11)]) is ErrorKind.TOO_MANY_EXAMS


def test_max_tokens_grow_with_pages_up_to_the_cap() -> None:
    small, big = exams.max_tokens([_exam("a", 1)]), exams.max_tokens([_exam("a", 60)])
    assert small < big == exams.EXAMS_MAX_TOKENS


def test_exam_key_ignores_order_level_and_exam_type(fx, tmp_path, cache) -> None:
    a = pipeline.prepare(
        fx.con_indice, _opts(tmp_path, exams=(fx.examen, fx.examen_escaneado)), cache, MODEL
    )
    b = pipeline.prepare(
        fx.con_indice,
        _opts(
            tmp_path,
            exams=(fx.examen_escaneado, fx.examen),
            nivel="completo",
            tipo_examen="test",
        ),
        cache,
        MODEL,
    )
    assert pipeline.exams_key(a) == pipeline.exams_key(b)


def test_book_is_not_its_own_exam(fx, tmp_path, cache) -> None:
    prep = pipeline.prepare(
        fx.con_indice, _opts(tmp_path, exams=(fx.con_indice, fx.examen)), cache, MODEL
    )
    assert [e.name for e in prep.exams] == ["examen.pdf"]


def test_replan_uses_exams_already_read_without_opening_files(fx, tmp_path, cache) -> None:
    prep = pipeline.prepare(fx.con_indice, _opts(tmp_path), cache, MODEL)
    gone = exams.read_exam(fx.examen)
    moved = tmp_path / "ya-no-esta.pdf"
    ghost = exams.Exam(moved, moved.name, gone.sha256, gone.pages, gone.text, ())
    again = pipeline.replan(prep, _opts(tmp_path, exams=(moved,)), cache, [ghost])
    assert [e.name for e in again.exams] == ["ya-no-esta.pdf"]


def test_unreadable_scanned_exam_does_not_stop_the_book(fx, tmp_path, cache) -> None:
    copy = tmp_path / "foto.pdf"
    copy.write_bytes(fx.examen_escaneado.read_bytes())
    opts = _opts(tmp_path, exams=(copy,))
    prep = pipeline.prepare(fx.con_indice, opts, cache, MODEL)
    copy.unlink()  # se borra entre la estimación y el procesado
    result = pipeline.run(prep, opts, FakeLLMClient(model=MODEL), cache)
    assert result.exams_failed
    assert result.libro.capitulos


def test_cached_exam_analysis_does_not_reopen_the_files(fx, tmp_path, cache) -> None:
    copy = tmp_path / "foto.pdf"
    copy.write_bytes(fx.examen_escaneado.read_bytes())
    opts = _opts(tmp_path, exams=(copy,))
    _run(fx.con_indice, tmp_path, cache, exams=(copy,))
    prep = pipeline.prepare(fx.con_indice, opts, cache, MODEL)
    copy.unlink()
    result = pipeline.run(prep, opts, FakeLLMClient(model=MODEL), cache)
    assert not result.exams_failed
    assert result.cached_calls == result.calls


def test_too_big_exam_set_is_rejected_in_replan(fx, tmp_path, cache) -> None:
    prep = pipeline.prepare(fx.con_indice, _opts(tmp_path), cache, MODEL)
    many = [_exam(str(i), 30) for i in range(3)]
    with pytest.raises(CribaError) as err:
        pipeline.replan(prep, _opts(tmp_path, exams=tuple(e.path for e in many)), cache, many)
    assert err.value.kind is ErrorKind.EXAMS_TOO_BIG
