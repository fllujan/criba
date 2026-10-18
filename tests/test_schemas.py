import json

import anthropic
import pytest
from pydantic import ValidationError

from criba.core import schemas


def _concepto(**kw):
    base = {
        "titulo": "Célula",
        "explicacion": "Unidad básica de la vida.",
        "tipo": "definicion",
        "importancia": 3,
        "paginas": [12, 11, 12],
        "cita_literal": "La célula es la unidad básica de la vida.",
    }
    return base | kw


def test_pages_sorted_and_deduplicated() -> None:
    c = schemas.Concepto.model_validate(_concepto())
    assert c.paginas == [11, 12]


def test_pages_outside_context_rejected_with_clear_error() -> None:
    with pytest.raises(ValidationError) as exc:
        schemas.Concepto.model_validate(_concepto(paginas=[99]), context={"paginas": (10, 20)})
    assert "99" in str(exc.value) and "10–20" in str(exc.value)


def test_pages_required() -> None:
    with pytest.raises(ValidationError):
        schemas.Concepto.model_validate(_concepto(paginas=[]))


def test_long_quote_truncated_to_40_words() -> None:
    c = schemas.Concepto.model_validate(_concepto(cita_literal=" ".join(["palabra"] * 60)))
    assert c.cita_literal is not None
    assert len(c.cita_literal.split()) == 41  # 40 + «[…]»


def test_empty_quote_becomes_none() -> None:
    assert schemas.Concepto.model_validate(_concepto(cita_literal="  ")).cita_literal is None


def test_extra_fields_rejected() -> None:
    with pytest.raises(ValidationError):
        schemas.Concepto.model_validate(_concepto(inventado=True))


def _pregunta(**kw):
    base = {
        "pregunta": "¿Qué es la célula?",
        "tipo": "test",
        "respuesta_clave": "La unidad básica.",
        "opciones": ["a", "b", "c", "d"],
        "correcta": 2,
        "paginas": [5],
        "motivo": "Definición formal.",
    }
    return base | kw


def test_test_question_needs_4_options_and_valid_answer() -> None:
    assert schemas.PreguntaProbable.model_validate(_pregunta()).correcta == 2
    with pytest.raises(ValidationError):
        schemas.PreguntaProbable.model_validate(_pregunta(opciones=["a", "b"]))
    with pytest.raises(ValidationError):
        schemas.PreguntaProbable.model_validate(_pregunta(correcta=4))
    with pytest.raises(ValidationError):
        schemas.PreguntaProbable.model_validate(_pregunta(correcta=None))


def test_non_test_question_drops_options() -> None:
    q = schemas.PreguntaProbable.model_validate(_pregunta(tipo="desarrollo"))
    assert q.opciones is None and q.correcta is None


def test_outline_max_three_levels_by_construction() -> None:
    hoja = {"texto": "c", "negrita": [], "paginas": [1]}
    medio = hoja | {"hijos": [hoja]}
    raiz = hoja | {"hijos": [medio]}
    schemas.NodoEsquema.model_validate(raiz)
    with pytest.raises(ValidationError):
        schemas.NodoEsquema.model_validate(hoja | {"hijos": [medio | {"hijos": [medio]}]})


def test_outline_pages_validated_in_nested_nodes() -> None:
    raiz = {
        "texto": "a",
        "negrita": [],
        "paginas": [1],
        "hijos": [{"texto": "b", "negrita": [], "paginas": [50], "hijos": []}],
    }
    with pytest.raises(ValidationError):
        schemas.NodoEsquema.model_validate(raiz, context={"paginas": (1, 10)})


def test_ocr_requires_all_pages() -> None:
    data = json.dumps({"paginas": [{"pagina": 1, "texto": "x"}]})
    schemas.OcrResultado.model_validate_json(data, context={"paginas_ocr": [1]})
    with pytest.raises(ValidationError):
        schemas.OcrResultado.model_validate_json(data, context={"paginas_ocr": [1, 2]})


def test_api_schemas_are_not_recursive_and_closed() -> None:
    for model in (
        schemas.ChunkAnalysis,
        schemas.SintesisCapitulo,
        schemas.SintesisLibro,
        schemas.OcrResultado,
    ):
        sch = anthropic.transform_schema(model)
        text = json.dumps(sch)
        for name, definition in sch.get("$defs", {}).items():
            assert f'"#/$defs/{name}"' not in json.dumps(definition), f"{name} es recursivo"
        assert '"additionalProperties": true' not in text
