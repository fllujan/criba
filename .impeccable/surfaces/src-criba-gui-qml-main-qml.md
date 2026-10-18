---
version: 1
slug: "src-criba-gui-qml-main-qml"
primary_target: "src/criba/gui/qml/Main.qml"
related_targets: ["src/criba/gui/qml"]
---

# Superficie: app de escritorio Criba (todas las pantallas)

Modo: Operate. Usuario: estudiante con prisa antes de un examen. Tarea: cargar el libro, confirmar el coste, recibir los dos PDF. Pantallas: asistente de clave, Inicio, Procesando, Listo, Ajustes, Historial.

## Direction contract

THESIS: La app es el cuaderno de la asignatura: una tapa verde con etiqueta y una hoja cuadriculada con margen donde se anotan las decisiones. Rechaza el esquema de categoría (barra lateral gris, tarjeta de arrastre con sombra, panel de resumen).

OWN-WORLD: Tapa de polipropileno en verde plano #4E6A17 a ancho completo; etiqueta blanca redondeada con la asignatura. Hoja blanca #FCFDFA con cuadrícula de 16 px muy tenue (#E3EBF1) visible en el margen y los huecos; filete de margen verde #6B8E23. Marcas a bolígrafo azul #1F3A8A en celdas fijas del margen. Inter para la interfaz, Source Serif 4 para lo que viene del libro. Filetes de 1 px, sin tarjetas flotantes, sin degradados ni sombras. En modo oscuro: tapa verde profundo y hoja pizarra, la misma geometría.

STORY: El estudiante ve su asignatura escrita en la tapa, revisa en la hoja qué capítulos entran y cuánto cuesta, y pulsa Generar con confianza; mientras procesa, los capítulos se van marcando en el margen; al final recoge sus dos PDF.

FIRST VIEWPORT: Banda-tapa arriba (64–88 px) con la etiqueta de la asignatura a la izquierda, pasos 1 Libro · 2 Procesar · 3 Listo en el centro, Historial y Ajustes a la derecha. Hoja debajo: margen de 112 px con números de sección rodeados y marcas; columna principal con archivo y lista de capítulos; columna derecha de unos 380 px con nivel, tipo de examen, estimación (coste grande) y el botón principal Generar a ancho completo de la columna.

FORM: Cuaderno de cuadros, candidato 5 de 7 de la lista propia; seed: seed:c115eaa59190d31f. Gesto distintivo: el margen como columna de estado (marca dibujada a bolígrafo en una celda fija: llena = incluido o hecho, hueca = pendiente o fuera, que se traza con un trazo animado al completarse; con movimiento reducido aparece sin animación). Raises: retícula de 16 px como estructura real (Crouwel); estado como marca en celda fija (horario); color plano a escala de región (plano de zoo); filetes de 1 px en lugar de tarjetas (web densa); lectura en vivo de coste y tiempo (espécimen).

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
