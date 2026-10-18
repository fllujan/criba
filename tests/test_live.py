"""Integración real contra la API de Anthropic (spec §9). Gasta saldo (céntimos).

Solo se ejecuta con ``ANTHROPIC_API_KEY`` presente:
``ANTHROPIC_API_KEY=... uv run pytest -m live -s``
Modelo: ``CRIBA_LIVE_MODEL`` (por defecto, el de la app).
"""

import os

import pytest

from criba.core import pipeline, schemas
from criba.core.cache import Cache
from criba.core.cost import DEFAULT_MODEL
from criba.core.llm import AnthropicClient
from tests.fixtures.build import build_small

API_KEY = os.environ.get("ANTHROPIC_API_KEY")  # se lee antes de que los fixtures la oculten
MODEL = os.environ.get("CRIBA_LIVE_MODEL", DEFAULT_MODEL)

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not API_KEY, reason="necesita ANTHROPIC_API_KEY"),
]


def test_real_book_end_to_end(tmp_path) -> None:
    pdf = build_small(tmp_path / "libro20.pdf")
    opts = pipeline.Options(asignatura="Biología general", output_dir=tmp_path / "out")
    with Cache(tmp_path / "cache.sqlite3") as cache:
        prep = pipeline.prepare(pdf, opts, cache, MODEL)
        assert API_KEY
        client = AnthropicClient(API_KEY, MODEL)
        result = pipeline.run(prep, opts, client, cache)

        libro = schemas.Libro.model_validate_json(result.json_path.read_text(encoding="utf-8"))
        assert libro.capitulos and not libro.paginas_no_procesadas
        for cap in libro.capitulos:
            a, b = cap.paginas
            assert cap.conceptos and cap.preguntas and cap.esquema
            for item in [*cap.conceptos, *cap.preguntas]:
                assert all(a <= p <= b for p in item.paginas)

        ratio = result.cost_usd / prep.estimate.usd
        print(
            f"\nCoste real {result.cost_usd:.4f} $ · estimado {prep.estimate.usd:.4f} $ "
            f"· ratio {ratio:.2f} · caché de prompts leída: {result.usage.cache_read} tokens"
        )
        assert 0.5 <= ratio <= 1.5, "recalibrar los supuestos de cost.py (objetivo ±25 %)"

        # Repetir no hace llamadas nuevas.
        again = pipeline.run(pipeline.prepare(pdf, opts, cache, MODEL), opts, client, cache)
        assert again.cost_usd == 0 and again.cached_calls == again.calls
