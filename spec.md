# Criba — Especificación técnica

Oct 18, 2026 · @Félix

## 1. Resumen del producto y objetivos

Criba es una aplicación de escritorio para macOS y Windows que convierte un libro en PDF en dos documentos de estudio: un resumen con lo que hay que estudiar y un esquema de examen con lo más importante y las preguntas probables. El nombre viene de cribar: separar el grano de la paja.

**Problema.** Los libros de texto mezclan contenido evaluable con ejemplos, digresiones y relleno. El estudiante pierde horas decidiendo qué estudiar antes de empezar a estudiar.

**Solución.** El usuario arrastra el PDF del libro a la ventana, pulsa Generar y recibe dos PDF maquetados. Opcionalmente puede añadir exámenes de años anteriores para afinar las prioridades.

**Objetivos medibles de la versión 1.0**

- Procesar un libro de texto de 300 páginas en menos de 15 minutos.
- El resumen ocupa entre el 10 % y el 20 % de las páginas del libro original.
- Cada punto del resumen y del esquema indica la página del libro de la que sale.
- Funciona igual en macOS (Apple Silicon e Intel) y Windows 10/11 de 64 bits.
- El usuario ve el coste estimado antes de procesar y nunca se le cobra dos veces el mismo fragmento.

**Fuera de alcance en la 1.0:** apps móviles, cuentas de usuario, sincronización en la nube, edición del resumen dentro de la app y formatos distintos de PDF (EPUB, DOCX).

## 2. Usuarios y casos de uso

El usuario principal es un estudiante (bachillerato, FP, universidad u oposiciones) sin conocimientos técnicos. La app debe poder usarse sin leer instrucciones.

| Caso de uso | Entrada | Salida | Frecuencia |
| --- | --- | --- | --- |
| CU1. Resumir un libro | 1 PDF de libro | Resumen PDF + Esquema PDF | Principal (90 %) |
| CU2. Resumir con exámenes antiguos | 1 PDF de libro + 1 o más PDF de exámenes | Igual, con prioridades ajustadas a lo que se ha preguntado | Ocasional |
| CU3. Resumir solo unos capítulos | 1 PDF + selección de capítulos o rango de páginas | Igual, limitado a la selección | Ocasional |
| CU4. Repetir un libro ya procesado | PDF ya procesado | Regenera los PDF desde la caché, sin coste de IA | Ocasional |

**Supuesto por defecto:** el usuario solo tiene el libro. Todo el diseño debe dar un buen resultado sin exámenes; los exámenes son una mejora opcional.

## 3. Requisitos funcionales

Prioridad: **M** = obligatorio en la 1.0, **S** = deseable en la 1.0, **C** = futuro.

| ID | Requisito | Prioridad |
| --- | --- | --- |
| RF-01 | Cargar un PDF arrastrándolo a la ventana o con el botón Elegir archivo. | M |
| RF-02 | Validar el PDF: que abra, que no esté protegido con contraseña, máximo 1.500 páginas y 500 MB. Mensaje claro si falla. | M |
| RF-03 | Extraer el texto de cada página. Detectar páginas escaneadas (sin texto) y leerlas con la visión de Claude. | M |
| RF-04 | Detectar capítulos y apartados: primero el índice interno del PDF; si no hay, por tamaño de letra de los títulos; si tampoco, por bloques de páginas. | M |
| RF-05 | Mostrar los capítulos detectados con casillas para elegir cuáles procesar (todos marcados por defecto) y un rango de páginas opcional. | S |
| RF-06 | Campo Nombre de la asignatura (se rellena con el título del PDF) que aparece en la portada de los PDF. | M |
| RF-07 | Selector de nivel de detalle: Esencial (≈10 % del libro), Normal (≈15 %), Completo (≈20 %). Por defecto Normal. | M |
| RF-08 | Selector de tipo de examen: Test, Desarrollo, Mixto (por defecto). Cambia el tipo de preguntas del esquema. | S |
| RF-09 | Añadir uno o varios PDF de exámenes antiguos (opcional). Si los hay, los temas preguntados suben de prioridad y se indica "Ha caído en examen". | S |
| RF-10 | Antes de procesar, mostrar páginas, número de llamadas y coste estimado en euros y dólares, con botón Confirmar. | M |
| RF-11 | Mostrar progreso por etapas (Leyendo, Analizando capítulo X de Y, Generando PDF) con barra y tiempo restante estimado. | M |
| RF-12 | Botón Cancelar. Lo ya procesado queda en caché y se reanuda sin volver a pagar. | M |
| RF-13 | Generar el PDF Resumen para estudiar (ver sección 7). | M |
| RF-14 | Generar el PDF Esquema de examen (ver sección 7). | M |
| RF-15 | Cada idea del resumen y del esquema incluye la página o páginas del libro original (p. 45 o pp. 45–47). | M |
| RF-16 | Al terminar: botones Abrir resumen, Abrir esquema y Mostrar en carpeta. | M |
| RF-17 | Pantalla de Ajustes: clave de API, modelo, carpeta de salida, idioma de los PDF (por defecto el del libro). | M |
| RF-18 | Historial de libros procesados con opción de volver a abrir o regenerar desde caché. | S |
| RF-19 | Generar tarjetas de repaso (flashcards) y exportarlas a Anki. | C |

**Regla de contenido clave:** la IA nunca inventa información que no esté en el libro. Si algo es una deducción (por ejemplo, una pregunta probable), se marca como tal.

## 4. Flujo de la aplicación y pantallas

La app tiene cuatro pantallas en una sola ventana (mínimo 900 × 640 px) y un flujo lineal de tres pasos: cargar, confirmar, recibir.

1. **Primer arranque.** Si no hay clave de API guardada, se abre un asistente de una sola página: qué es la clave, enlace a console.anthropic.com para obtenerla, campo para pegarla y botón Probar conexión. Sin clave válida no se puede continuar.
2. **Pantalla Inicio.** Zona grande de arrastrar y soltar con el texto "Arrastra aquí tu libro en PDF". Debajo, un enlace secundario "Añadir exámenes antiguos (opcional)". Al soltar el PDF se analiza localmente (sin coste) y aparecen:
   - Nombre de la asignatura (editable).
   - Lista de capítulos detectados con casillas.
   - Nivel de detalle y tipo de examen.
   - Resumen: páginas, páginas escaneadas, tiempo y coste estimados.
   - Botón principal Generar.
3. **Pantalla Procesando.** Barra de progreso, etapa actual, capítulo actual, tiempo restante y coste acumulado. Botón Cancelar con confirmación.
4. **Pantalla Listo.** Miniatura de la primera página de cada PDF, botones Abrir resumen, Abrir esquema, Mostrar en carpeta y Procesar otro libro.
5. **Ajustes** (icono de engranaje, accesible siempre): clave de API (oculta, con botón Cambiar), modelo, carpeta de salida (por defecto Documentos/Criba), idioma de salida, borrar caché.
6. **Historial** (S): lista de libros procesados con fecha, botones Abrir y Regenerar.

**Diseño visual.** Limpio y tranquilo: fondo claro, un color de acento (verde trigo, #6B8E23), tipografía del sistema, modo oscuro automático. Textos de la interfaz en español; preparar la estructura para traducciones (archivos .ts de Qt).

**Errores en la interfaz.** Nunca se muestra un error técnico crudo. Cada error tiene un mensaje en lenguaje normal y una acción: Reintentar, Cambiar clave, Elegir otro archivo. El detalle técnico va al log.

## 5. Arquitectura y stack tecnológico (Mac y Windows)

Una sola base de código en Python 3.12 con interfaz Qt, empaquetada por separado para cada sistema. Todas las dependencias elegidas funcionan en macOS y Windows sin instalar nada aparte.

| Capa | Tecnología | Motivo |
| --- | --- | --- |
| Lenguaje | Python 3.12 | Mejores librerías de PDF e IA; un solo código para los dos sistemas. |
| Interfaz | PySide6 (Qt 6) | Nativa en Mac y Windows, modo oscuro, arrastrar y soltar, licencia LGPL. |
| Lectura de PDF | PyMuPDF | Rápida; extrae texto, índice, tamaños de letra y renderiza páginas a imagen. |
| IA | SDK oficial `anthropic` | Claude API con salida JSON validada. |
| Modelo por defecto | `claude-sonnet-5-5` | Buen equilibrio entre calidad y coste. Configurable en Ajustes (`claude-haiku-5-5` más barato, `claude-opus-5-5` más preciso). |
| Validación de datos | Pydantic v2 | Esquemas de las respuestas de la IA; reintento si el JSON no cumple. |
| Generación de PDF | ReportLab (Platypus) | Python puro, sin dependencias del sistema, control total de la maquetación. |
| Fuentes | Inter y Source Serif 4, incluidas en la app | Mismo aspecto en ambos sistemas; soportan tildes y ñ. |
| Clave de API | `keyring` | Llavero de macOS y Administrador de credenciales de Windows. Nunca en texto plano. |
| Caché | SQLite (`sqlite3` estándar) | Resultados por fragmento, indexados por hash; permite reanudar y regenerar gratis. |
| Ajustes | `platformdirs` + JSON | Rutas correctas en cada sistema. |
| Empaquetado | PyInstaller | `.app` en un `.dmg` para Mac, `.exe` con instalador Inno Setup para Windows. |
| Tests | pytest + pytest-qt | Unitarios, integración y de interfaz. |

**Separación por capas.** El núcleo (`core/`) no importa nada de Qt: se puede usar desde la línea de comandos y testear sin interfaz. La interfaz (`gui/`) solo llama al núcleo y escucha sus eventos de progreso. El trabajo pesado corre en un hilo aparte (`QThread`) para que la ventana nunca se congele.

**Estructura del repositorio**

```text
criba/
├── pyproject.toml
├── README.md
├── src/criba/
│   ├── __main__.py          # arranque de la GUI
│   ├── cli.py               # uso por línea de comandos (desarrollo y tests)
│   ├── core/
│   │   ├── ingest.py        # validación y extracción de texto
│   │   ├── ocr.py           # páginas escaneadas vía visión de Claude
│   │   ├── structure.py     # detección de capítulos y fragmentación
│   │   ├── llm.py           # cliente de Claude, reintentos, coste
│   │   ├── prompts/         # plantillas de prompts (.md)
│   │   ├── schemas.py       # modelos Pydantic
│   │   ├── analyze.py       # etapas map y reduce
│   │   ├── exams.py         # análisis de exámenes antiguos
│   │   ├── cache.py         # SQLite
│   │   ├── cost.py          # estimación de tokens y coste
│   │   └── pipeline.py      # orquestación y eventos de progreso
│   ├── render/
│   │   ├── styles.py        # colores, fuentes, márgenes
│   │   ├── summary_pdf.py   # PDF Resumen para estudiar
│   │   └── outline_pdf.py   # PDF Esquema de examen
│   ├── gui/
│   │   ├── main_window.py
│   │   ├── screens/         # inicio, procesando, listo, ajustes, historial
│   │   └── worker.py        # QThread que ejecuta el pipeline
│   └── assets/              # fuentes, iconos, traducciones
├── tests/
│   ├── fixtures/            # PDFs de prueba
│   └── ...
├── packaging/
│   ├── criba.spec           # PyInstaller
│   ├── macos/               # Info.plist, icono .icns, script del .dmg
│   └── windows/             # icono .ico, script de Inno Setup
└── .github/workflows/build.yml
```

## 6. Pipeline de procesamiento del PDF y prompts de IA

El libro se procesa en siete etapas con un patrón map-reduce: primero se analiza cada fragmento por separado y luego se combinan los resultados por capítulo y por libro. Así un libro de cualquier tamaño cabe en los límites del modelo.

&#91;embedded content: pipeline de Criba · 7 etapas, 3 con IA\]

Las etapas 3, 5 y 6 son las únicas que cuestan dinero, y sus resultados se guardan en caché para no pagarlos dos veces.

### Etapas

1. **Ingesta (local, gratis).** Abrir con PyMuPDF, validar (RF-02), calcular el hash SHA-256 del archivo para la caché.
2. **Extracción (local, gratis).** Texto por página con `page.get_text("dict")`, conservando tamaño de letra y negritas. Limpiar cabeceras y pies repetidos (líneas que aparecen en más del 50 % de las páginas) y números de página. Una página con menos de 80 caracteres útiles e imágenes se marca como escaneada.
3. **OCR de páginas escaneadas (IA).** Renderizar a 150 ppp y enviar a Claude como imagen con el prompt `ocr.md`, por lotes de 5 páginas. Resultado: texto plano por página.
4. **Estructura (local, gratis).** Capítulos y apartados desde `doc.get_toc()`. Si no hay índice: títulos por tamaño de letra (≥ 1,3 veces la mediana del texto). Si tampoco: bloques de 20 páginas. Cada capítulo se divide en fragmentos de máximo 12.000 tokens, cortando siempre entre párrafos y con 300 tokens de solapamiento.
5. **Map: análisis por fragmento (IA).** Cada fragmento se envía con el prompt `analyze_chunk.md` y devuelve un `ChunkAnalysis` en JSON. Hasta 4 llamadas en paralelo.
6. **Reduce: síntesis por capítulo y global (IA).** Por capítulo, `synthesize_chapter.md` fusiona los fragmentos, elimina duplicados y fija prioridades. Al final, `synthesize_book.md` añade el mapa general del libro y las conexiones entre temas. Si hay exámenes, `exams.md` los analiza antes y su resultado entra en esta etapa.
7. **Render (local, gratis).** Generar los dos PDF a partir del JSON final (sección 7).

Cada llamada a la IA se guarda en la caché con clave `hash(PDF) + id_fragmento + versión_prompt + modelo + nivel_detalle`. Si se cancela o falla, al repetir solo se procesan los fragmentos que faltan.

### Esquemas de datos (Pydantic)

```python
class Concepto(BaseModel):
    titulo: str
    explicacion: str              # 1-3 frases, en palabras propias
    tipo: Literal["definicion", "idea_clave", "formula", "fecha", "clasificacion", "proceso", "autor", "dato"]
    importancia: Literal[1, 2, 3]  # 3 = imprescindible
    paginas: list[int]
    cita_literal: str | None      # solo definiciones y fórmulas, máx. 40 palabras

class PreguntaProbable(BaseModel):
    pregunta: str
    tipo: Literal["test", "corta", "desarrollo", "problema"]
    respuesta_clave: str          # guion de respuesta, 2-5 frases
    opciones: list[str] | None    # 4 opciones si tipo == "test"
    correcta: int | None
    paginas: list[int]
    motivo: str                   # por qué es probable

class ChunkAnalysis(BaseModel):
    conceptos: list[Concepto]
    preguntas: list[PreguntaProbable]
    paja: list[str]               # qué se ha descartado, en una línea cada cosa

class Capitulo(BaseModel):
    titulo: str
    paginas: tuple[int, int]
    prioridad: Literal["alta", "media", "baja"]
    resumen: str                  # 1 párrafo
    esquema: list[NodoEsquema]    # árbol jerárquico, máx. 3 niveles
    conceptos: list[Concepto]
    preguntas: list[PreguntaProbable]
    ha_caido_en_examen: bool
```

### Reglas de los prompts

Los prompts viven en `core/prompts/` como archivos Markdown versionados (`analyze_chunk.v1.md`). Todos cumplen estas reglas:

- **Rol:** "Eres un profesor experto que prepara a un alumno para el examen de {asignatura}".
- **Fidelidad:** usar solo información del texto dado. Prohibido añadir conocimiento externo. Cada concepto lleva sus páginas.
- **Qué es grano:** definiciones, conceptos en negrita o cursiva, clasificaciones y listas numeradas, fórmulas, fechas y autores, procesos paso a paso, conclusiones de cada apartado, todo lo que el autor resume o repite.
- **Qué es paja:** anécdotas, ejemplos repetidos (se conserva el mejor), introducciones motivacionales, historias de contexto sin datos evaluables, recapitulaciones redundantes.
- **Importancia 3** si aparece en un título, en negrita, en un resumen de capítulo o se repite en varios apartados.
- **Preguntas probables:** basadas en señales del texto (definiciones formales, listas, comparaciones, "es importante destacar"). El campo `motivo` explica la señal.
- **Nivel de detalle:** el prompt recibe el porcentaje objetivo (10/15/20 %) y lo respeta.
- **Idioma:** responder en el idioma del libro salvo que Ajustes indique otro.
- **Salida:** solo JSON conforme al esquema, mediante tool use con `input_schema`. Si la validación de Pydantic falla, un reintento con el error incluido; si vuelve a fallar, se registra y el fragmento se marca como fallido.

### Llamadas a la API

- Reintentos con espera exponencial (1, 2, 4, 8 y 16 s) ante errores 429, 500, 529 y de red.
- Prompt caching del bloque de instrucciones del sistema para abaratar las llamadas repetidas.
- Registro de tokens de entrada y salida de cada llamada para el coste real.
- Estimación previa: tokens ≈ caracteres / 3,5; coste = tokens × precio del modelo, con tabla de precios en `cost.py` fácil de actualizar.

## 7. Formato de los PDF de salida

Ambos PDF son A4, con marcadores navegables (índice lateral del lector de PDF), enlaces internos desde el índice y números de página. Nombre de archivo: `{Asignatura} - Resumen.pdf` y `{Asignatura} - Esquema de examen.pdf`.

### PDF 1: Resumen para estudiar

1. **Portada:** asignatura, título del libro, fecha, nivel de detalle, "Generado con Criba".
2. **Índice** con prioridad de cada capítulo (Alta, Media, Baja) y páginas.
3. **Mapa del libro:** una página que resume de qué va el libro y cómo se conectan los temas.
4. **Por capítulo:**
   - Título, páginas del libro y etiqueta de prioridad en color.
   - Resumen del capítulo en un párrafo.
   - Ideas clave ordenadas por importancia: imprescindible (★★★), importante (★★), complementario (★).
   - Definiciones en recuadros con fondo suave.
   - Fórmulas en recuadro centrado.
   - Cada elemento termina con la referencia (p. 45) en gris.
   - "Lo que puedes saltarte": una lista breve de la paja descartada, para que el alumno confíe en el recorte.

### PDF 2: Esquema de examen

1. **Portada** igual que el resumen.
2. **Prioridades de estudio:** tabla de capítulos ordenados de más a menos importante, con horas de estudio relativas recomendadas.
3. **Por capítulo:**
   - Esquema jerárquico de hasta 3 niveles con viñetas y sangrías, palabras clave en negrita. Debe caber en 1 o 2 páginas por capítulo.
   - Preguntas probables numeradas, con su tipo (Test, Corta, Desarrollo, Problema) y el guion de respuesta debajo.
   - Las preguntas tipo test van con 4 opciones; la correcta, en las soluciones al final del PDF.
   - Etiqueta "Ha caído en examen" en los temas que aparecen en exámenes antiguos (si se añadieron).
4. **Checklist final:** lista con casillas de todos los conceptos imprescindibles (★★★) para marcar a mano al repasar.
5. **Soluciones** de las preguntas tipo test.

### Estilo

| Elemento | Valor |
| --- | --- |
| Márgenes | 2 cm |
| Texto | Source Serif 4, 10,5 pt, interlineado 1,35 |
| Títulos | Inter Semibold: 20 / 15 / 12 pt |
| Acento | Verde trigo #6B8E23 |
| Prioridad Alta / Media / Baja | #C0392B / #D68910 / #7F8C8D |
| Recuadros de definición | Fondo #F4F7EC, borde izquierdo de 3 pt en el acento |
| Referencias de página | 9 pt, gris #7F8C8D |

El PDF debe imprimirse bien en blanco y negro: la prioridad nunca se indica solo con color, siempre también con texto o estrellas.

## 8. Requisitos no funcionales, errores y seguridad

| ID | Requisito |
| --- | --- |
| RNF-01 | Rendimiento: 300 páginas de texto en menos de 15 min con el modelo por defecto; la ventana responde siempre en menos de 100 ms. |
| RNF-02 | Memoria: máximo 1 GB de RAM con un PDF de 1.500 páginas (procesar página a página, no cargarlo todo). |
| RNF-03 | Privacidad: el libro solo sale del ordenador hacia la API de Anthropic. Sin telemetría ni analíticas. Se explica en Ajustes. |
| RNF-04 | Seguridad: clave de API en el llavero del sistema (`keyring`), nunca en archivos, logs ni mensajes de error. |
| RNF-05 | Robustez: un fragmento fallido no detiene el proceso; se reintenta al final y, si sigue fallando, el PDF incluye una nota "Páginas X–Y no procesadas". |
| RNF-06 | Reanudación: si la app se cierra a mitad, al volver ofrece Continuar donde lo dejaste. |
| RNF-07 | Logs rotativos (5 archivos × 2 MB) en la carpeta de datos de la app, accesibles desde Ajustes > Abrir carpeta de logs. |
| RNF-08 | Accesibilidad: navegable con teclado, contraste AA, tamaños de letra del sistema respetados. |
| RNF-09 | Calidad de código: tipado completo, `ruff` y `mypy --strict` sin errores, cobertura de tests ≥ 80 % en `core/` y `render/`. |

### Errores previstos y mensaje al usuario

| Situación | Mensaje | Acción |
| --- | --- | --- |
| PDF con contraseña | Este PDF está protegido con contraseña. | Elegir otro archivo |
| PDF dañado o no es PDF | No se ha podido abrir este archivo. | Elegir otro archivo |
| Clave de API no válida (401) | La clave de API no es válida o ha caducado. | Cambiar clave |
| Sin saldo en la cuenta (400/402 de facturación) | Tu cuenta de Anthropic no tiene saldo suficiente. | Abrir consola, Reintentar |
| Sin conexión | No hay conexión a Internet. Lo procesado se ha guardado. | Reintentar |
| Límite de uso (429) persistente | El servicio está saturado. Se reintentará automáticamente. | Esperar, Cancelar |
| Disco lleno al guardar | No hay espacio para guardar el PDF. | Elegir otra carpeta |
| Libro sin texto útil | No se ha encontrado texto en este PDF. | Elegir otro archivo |

## 9. Empaquetado, distribución y tests

### Empaquetado

|  | macOS | Windows |
| --- | --- | --- |
| Formato | `Criba.app` dentro de `Criba-x.y.z.dmg` | `Criba-Setup-x.y.z.exe` (Inno Setup) |
| Arquitecturas | Universal 2 (Apple Silicon + Intel) o dos builds separados | x64 |
| Mínimo | macOS 12 | Windows 10 64 bits |
| Icono | `criba.icns` | `criba.ico` |
| Firma | Firma con Developer ID y notarización (opcional en 1.0; sin ella, documentar clic derecho > Abrir) | Firma de código opcional; sin ella, documentar el aviso de SmartScreen |

Los builds se generan con GitHub Actions: un job `macos-14` y otro `windows-latest` que instalan dependencias, pasan los tests, ejecutan PyInstaller y suben el `.dmg` y el `.exe` como artefactos. Al crear una etiqueta `v*` se publican en GitHub Releases.

Para desarrollo local: `uv sync` (o `pip install -e .[dev]`) y `python -m criba`. Modo línea de comandos: `python -m criba.cli libro.pdf --nivel normal --salida ./out`.

### Tests

- **PDFs de prueba en `tests/fixtures/`:** uno con índice interno, uno sin índice, uno escaneado de 5 páginas, uno protegido con contraseña, uno dañado y uno largo generado (500 páginas). Generarlos con scripts propios para no usar material con derechos de autor.
- **Unitarios:** limpieza de cabeceras, detección de capítulos, fragmentación (ningún fragmento supera el límite, nunca corta a mitad de párrafo), estimación de coste, caché.
- **IA simulada:** un `FakeLLMClient` que devuelve JSON fijo. Todo el pipeline se testea sin gastar ni conectarse.
- **Integración real (opcional):** marcados `@pytest.mark.live`, solo se ejecutan con `ANTHROPIC_API_KEY` presente, sobre un libro de 20 páginas.
- **Render:** generar los dos PDF desde un JSON de ejemplo y comprobar que abren, que tienen marcadores y que contienen los títulos esperados.
- **Interfaz:** con pytest-qt, cargar un PDF, comprobar la pantalla de confirmación y el cambio a Listo usando el cliente simulado.

## 10. Plan de implementación por fases y criterios de aceptación

Cada fase termina con tests en verde y algo que se puede probar. No se empieza una fase sin cerrar la anterior.

| Fase | Entregable | Hecho cuando |
| --- | --- | --- |
| F0. Base | Repositorio, `pyproject.toml`, ruff, mypy, pytest, CI que pasa en Mac y Windows | El CI está en verde en los dos sistemas |
| F1. Lectura | `ingest`, `structure`, limpieza, fragmentación, fixtures | Los 6 PDFs de prueba se leen o rechazan correctamente |
| F2. IA | `llm`, `schemas`, prompts v1, `analyze` map y reduce, caché, coste, OCR | `python -m criba.cli` genera el JSON final de un libro de prueba; repetirlo no hace llamadas nuevas |
| F3. PDFs | `render/` con los dos PDF completos | Los dos PDF cumplen la sección 7 y se imprimen bien en blanco y negro |
| F4. Interfaz | Las pantallas de la sección 4 y el worker en segundo plano | Un usuario sin instrucciones procesa un libro de principio a fin |
| F5. Exámenes | `exams.py` y su integración | Con un examen antiguo, los temas preguntados suben de prioridad y llevan la etiqueta |
| F6. Distribución | PyInstaller, `.dmg`, instalador `.exe`, release automática | Los instaladores funcionan en un Mac y un PC limpios, sin Python instalado |

### Criterios de aceptación de la 1.0

- [ ] Un libro de 300 páginas con índice se procesa en menos de 15 minutos y genera los dos PDF.
- [ ] Un libro sin índice interno se divide en capítulos coherentes.
- [ ] Las páginas escaneadas se leen y su contenido aparece en el resumen.
- [ ] El resumen ocupa entre el 10 % y el 20 % del libro según el nivel elegido.
- [ ] Todas las ideas llevan referencia de página y, revisadas 20 al azar, al menos 19 apuntan a la página correcta.
- [ ] Ninguna idea revisada contiene información que no esté en el libro.
- [ ] Cancelar y reanudar no repite llamadas ya pagadas.
- [ ] El coste real final no se desvía más de un 25 % del estimado.
- [ ] La clave de API no aparece en ningún archivo del disco ni en los logs.
- [ ] Los instaladores de Mac y Windows funcionan en máquinas sin Python.

## 11. Instrucciones para Claude al construirlo

Esta sección va dirigida a Claude (Claude Code o el agente que construya el proyecto). Pégala junto con el resto del documento.

```markdown
Vas a construir "Criba", una app de escritorio para macOS y Windows descrita en esta especificación.

Forma de trabajar:
1. Lee la especificación entera antes de escribir código. Si algo es ambiguo o contradictorio, pregunta antes de decidir.
2. Trabaja fase a fase (sección 10). Al terminar cada fase: ejecuta ruff, mypy y pytest, corrige todo, haz commit con un mensaje claro y resume qué has hecho y cómo probarlo.
3. Respeta la estructura del repositorio de la sección 5. El núcleo (core/, render/) no importa nada de Qt.
4. Escribe tests a la vez que el código. Usa FakeLLMClient para que los tests no gasten dinero.
5. Nunca escribas la clave de API en código, archivos, logs ni tests. Léela de keyring o de la variable ANTHROPIC_API_KEY en desarrollo.
6. Los prompts van en archivos .md versionados en core/prompts/, no incrustados en el código.
7. Consulta la documentación actual del SDK anthropic, PySide6, PyMuPDF, ReportLab y PyInstaller antes de usarlos; no te fíes de APIs recordadas.
8. Todo texto visible para el usuario va en español y pasa por las funciones de traducción de Qt.
9. Comprueba el funcionamiento en los dos sistemas mediante el CI de GitHub Actions; nada de rutas ni comandos exclusivos de un sistema.
10. No añadas funciones fuera de esta especificación sin preguntar. Si propones una mejora, explícala y espera aprobación.

Empieza por la fase F0 y enséñame el resultado antes de seguir.
```

**Datos que debe aportar el dueño del proyecto:** una clave de API de Anthropic con saldo, un repositorio en GitHub y, si se quiere firmar las apps, un certificado de Apple Developer y otro de firma de código para Windows.
