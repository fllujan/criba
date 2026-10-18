"""Estimación de tokens y coste (F2 añade la tabla de precios)."""

import math

CHARS_PER_TOKEN = 3.5


def estimate_tokens(text: str) -> int:
    """Tokens aproximados: caracteres / 3,5, redondeando hacia arriba."""
    return math.ceil(len(text) / CHARS_PER_TOKEN)
