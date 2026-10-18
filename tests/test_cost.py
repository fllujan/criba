import pytest

from criba.core import cost
from criba.core.cost import ChapterPlan, ChunkPlan, Usage, estimate, estimate_tokens


def test_estimate_tokens_chars_over_3_5() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("a" * 35) == 10
    assert estimate_tokens("a" * 36) == 11  # redondea hacia arriba


def test_usage_cost_uses_model_prices() -> None:
    u = Usage(input=1_000_000, output=1_000_000, cache_write=1_000_000, cache_read=1_000_000)
    assert u.cost_usd("claude-sonnet-5-5") == pytest.approx(2 + 10 + 2.5 + 0.2)
    assert (
        u.cost_usd("claude-haiku-5-5")
        < u.cost_usd("claude-sonnet-5-5")
        < u.cost_usd("claude-opus-5-5")
    )


def test_usage_add() -> None:
    u = Usage(1, 2, 3, 4)
    u += Usage(10, 20, 30, 40)
    assert (u.input, u.output, u.cache_write, u.cache_read) == (11, 22, 33, 44)


def test_eur_conversion() -> None:
    assert cost.to_eur(100) == pytest.approx(100 * cost.USD_TO_EUR)


def test_target_words_by_level() -> None:
    assert (
        cost.target_words(100, "esencial")
        < cost.target_words(100, "normal")
        < (cost.target_words(100, "completo"))
    )
    assert cost.target_words(10, "normal") == round(10 * 0.15 * cost.WORDS_PER_PAGE)


def test_estimate_counts_calls_map_reduce_book() -> None:
    chapters = [
        ChapterPlan([ChunkPlan(10_000, 20), ChunkPlan(8_000, 15)]),
        ChapterPlan([ChunkPlan(5_000, 10)]),
    ]
    est = estimate(
        model="claude-sonnet-5-5", level="normal", system_tokens=1_500, chapters=chapters
    )
    assert est.calls == 3 + 2 + 1
    assert est.cached_calls == 0
    assert est.usage.input > 23_000
    assert 0 < est.eur < est.usd


def test_cached_calls_are_free() -> None:
    chapters = [ChapterPlan([ChunkPlan(10_000, 20, cached=True)], cached=True)]
    est = estimate(
        model="claude-sonnet-5-5",
        level="normal",
        system_tokens=1_500,
        chapters=chapters,
        book_cached=True,
    )
    assert est.calls == 3 and est.cached_calls == 3
    assert est.usd == 0


def test_cached_chunks_do_not_make_synthesis_free() -> None:
    chapters = [ChapterPlan([ChunkPlan(10_000, 20, cached=True)], cached=False)]
    est = estimate(
        model="claude-sonnet-5-5", level="normal", system_tokens=1_500, chapters=chapters
    )
    assert est.cached_calls == 1 and est.usd > 0


def test_more_detail_costs_more() -> None:
    chapters = [ChapterPlan([ChunkPlan(10_000, 30)])]
    costs = [
        estimate(model="claude-sonnet-5-5", level=lvl, system_tokens=1000, chapters=chapters).usd
        for lvl in ("esencial", "normal", "completo")
    ]
    assert costs == sorted(costs) and costs[0] < costs[2]


def test_ocr_batches_in_estimate() -> None:
    est = estimate(
        model="claude-sonnet-5-5",
        level="normal",
        system_tokens=500,
        chapters=[],
        ocr_batches=[(5, False), (2, True)],
    )
    assert est.calls == 2 and est.cached_calls == 1
    assert est.usage.input == 500 + 5 * cost.OCR_INPUT_PER_PAGE


def test_empty_chapters_skipped() -> None:
    est = estimate(
        model="claude-sonnet-5-5", level="normal", system_tokens=500, chapters=[ChapterPlan([])]
    )
    assert est.calls == 0


def test_default_model_is_priced() -> None:
    assert cost.DEFAULT_MODEL in cost.PRICES


def test_time_estimate() -> None:
    """RF-10 / RNF-01: un libro de 300 páginas, en menos de 15 minutos."""
    pages_per_chunk, chunks = 10, 30
    chapters = [ChapterPlan([ChunkPlan(9_000, pages_per_chunk)] * 3) for _ in range(chunks // 3)]
    est = estimate(
        model="claude-sonnet-5-5", level="normal", system_tokens=1_500, chapters=chapters
    )
    assert 60 < est.seconds < 15 * 60
    cached = estimate(
        model="claude-sonnet-5-5",
        level="normal",
        system_tokens=1_500,
        chapters=[ChapterPlan([ChunkPlan(9_000, 10, cached=True)], cached=True)],
        book_cached=True,
    )
    assert cached.seconds == 0
