from criba.core.cost import estimate_tokens


def test_estimate_tokens_chars_over_3_5() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("a" * 35) == 10
    assert estimate_tokens("a" * 36) == 11  # redondea hacia arriba
