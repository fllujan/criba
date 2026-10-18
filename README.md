# Criba

Criba convierte un libro de texto en PDF en dos documentos de estudio:

- **Resumen para estudiar**: lo que hay que saber, ordenado por importancia y con la página del libro en cada idea.
- **Esquema de examen**: lo más importante en forma de esquema, con preguntas probables y una checklist de repaso.

App de escritorio para **macOS** (Apple Silicon e Intel) y **Windows 10/11**. Usa la API de Claude (Anthropic). El libro solo sale de tu ordenador hacia la API de Anthropic. No hay telemetría.

> Estado: en desarrollo. Ya funcionan la lectura del PDF, el análisis con IA, los dos PDF, la interfaz y los exámenes antiguos (F1–F5). La especificación completa está en [`spec.md`](spec.md).

## Desarrollo

Requisitos: [uv](https://docs.astral.sh/uv/). uv instala Python 3.12 por su cuenta.

```bash
uv sync                      # crea .venv con todas las dependencias
uv run pre-commit install    # pasa ruff y mypy en cada commit
uv run python -m criba       # abre la app
uv run python -m criba.cli libro.pdf --nivel normal --salida ./out
```

### Línea de comandos

```bash
criba libro.pdf --solo-analisis            # capítulos y coste estimado, sin gastar
criba libro.pdf --simulado --si            # todo el proceso con IA simulada (gratis)
criba libro.pdf                            # proceso real: pide confirmación antes de gastar
criba libro.pdf --capitulos 2,3 --paginas 10-80 --nivel completo --examen test
criba libro.pdf --examenes junio.pdf septiembre.pdf  # lo que ha caído sube de prioridad
```

La clave de API se lee de `ANTHROPIC_API_KEY` o del llavero del sistema. Lo procesado se guarda en caché: si cancelas (Ctrl+C) o repites el mismo libro, lo ya pagado no se vuelve a pagar.

### Interfaz

```bash
uv run python -m criba                                    # la app
CRIBA_THEME=dark uv run python -m criba                   # forzar modo oscuro (o light)
uv run python scripts/screenshots.py capturas/ [--dark] [--size 900x640]  # capturas con IA simulada
uv run python scripts/update_translations.py              # actualiza assets/i18n/*.ts
```

El diseño («Cuaderno de cuadros») está documentado en `DESIGN.md`; los tokens viven en `src/criba/gui/qml/Criba/Theme.qml`.

### Calidad

```bash
uv run ruff format . && uv run ruff check .
uv run mypy                  # modo strict
uv run pytest --cov          # cobertura mínima del 80 %
uv run pytest -m live        # pruebas contra la API real (necesitan ANTHROPIC_API_KEY y gastan saldo)
```

## Arquitectura

| Carpeta | Qué hace |
| --- | --- |
| `src/criba/core/` | Lectura del PDF, estructura, IA, caché y coste. **No importa Qt.** |
| `src/criba/render/` | Genera los PDF de salida con ReportLab. **No importa Qt.** |
| `src/criba/gui/` | Interfaz Qt Quick (QML) con PySide6, y el worker en segundo plano. |
| `tests/` | pytest y pytest-qt. La IA se simula con `FakeLLMClient`, así que los tests no gastan saldo. |
| `packaging/` | PyInstaller, `.dmg` e instalador de Inno Setup. |

Un test (`tests/test_architecture.py`) comprueba que `core/` y `render/` no importan Qt.

## Seguridad

La clave de API se guarda en el llavero del sistema (Llavero de macOS o Administrador de credenciales de Windows). Nunca se escribe en archivos ni en los logs. Los logs ocultan automáticamente cualquier clave `sk-ant-…`.
