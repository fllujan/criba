# Criba — instrucciones para Claude

La especificación es `spec.md`. Plan de fases: §10. Consúltala antes de cada fase.

## Forma de trabajar
- Una fase cada vez (F0 a F6). Al cerrarla: `uv run ruff format . && uv run ruff check . && uv run mypy && uv run pytest --cov`, todo en verde. Después, commit claro y resumen para Félix con cómo probarlo. **Espera su OK antes de empezar la siguiente fase.**
- TDD: primero el test, luego el código.
- `core/` y `render/` **nunca** importan PySide6 (lo vigilan ruff TID251 y `tests/test_architecture.py`).
- La IA en tests es siempre `FakeLLMClient`. Los tests reales llevan `@pytest.mark.live`.
- Clave de API: solo `keyring` o `ANTHROPIC_API_KEY`. Nunca en código, archivos, logs, tests ni mensajes de error.
- Los prompts van en `src/criba/core/prompts/*.vN.md`, nunca incrustados en el código.
- Todo texto visible para el usuario va en español, con `qsTr()` en QML o `QCoreApplication.translate` en Python.
- Nada de rutas ni comandos propios de un solo sistema: usa `pathlib` y `criba.paths`.
- Antes de usar el SDK `anthropic`, PySide6/QML, PyMuPDF, ReportLab o PyInstaller, consulta su documentación actual (ctx7 / skill `claude-api`).
- No añadas funciones fuera del spec sin preguntar.
- No ejecutes `ruff format` sobre `spec.md`: ruff solo incluye `*.py`.

## Interfaz
- Qt Quick (QML) con el estilo `Basic` y un sistema de diseño propio. Acento: verde trigo `#6B8E23`. Modo oscuro automático. Mínimo 900 × 640.
- Diseño revisado con **Impeccable** (`/impeccable critique`, `audit`, `animate`, `polish`). El contexto está en `PRODUCT.md` y `DESIGN.md`.
- Las animaciones deben respetar la preferencia de "reducir movimiento" y no bloquear nunca la interfaz.
