# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

(Impeccable solo admite web, ios, android o adaptive; Criba dibuja su propio lenguaje visual como una web, aunque es una app de escritorio en Qt Quick, así que el valor correcto es `web`.) App de escritorio nativa para macOS 12+ (Apple Silicon e Intel) y Windows 10/11 x64. Tiene un único lenguaje visual propio de Criba, idéntico en los dos sistemas (decisión del dueño), y respeta las convenciones de cada plataforma: ⌘ en Mac y Ctrl en Windows, modo oscuro del sistema, tamaños de letra del sistema, arrastrar y soltar archivos, y abrir archivos y carpetas con el gestor nativo.

## Stack

Python 3.12 + PySide6 (Qt 6) con interfaz **Qt Quick / QML**, estilo `Basic` y un sistema de diseño propio. El núcleo (PyMuPDF, SDK `anthropic`, Pydantic, ReportLab) no importa Qt. Se empaqueta con PyInstaller (`.dmg` y un instalador de Inno Setup). La decisión de usar QML en lugar de Widgets la tomó el dueño, por las animaciones.

## Users

Estudiantes de bachillerato, FP, universidad u oposiciones, sin conocimientos técnicos. Llegan con un libro de texto en PDF y poco tiempo antes de un examen. Su trabajo es saber qué tienen que estudiar sin perder horas separando lo evaluable del relleno. Tienen que poder usar la app sin leer instrucciones.

## Product Purpose

Criba convierte un libro en PDF en dos documentos de estudio: un **Resumen para estudiar** (entre el 10 % y el 20 % del libro, ordenado por importancia) y un **Esquema de examen** (esquema jerárquico, preguntas probables, checklist de lo imprescindible y soluciones). Su nombre viene de *cribar*, separar el grano de la paja. El éxito es que el estudiante empiece a estudiar lo importante en minutos y confíe en el recorte.

## Positioning

Fidelidad verificable: cada idea indica la página del libro de la que sale (p. 45, pp. 45–47), la IA nunca añade información que no esté en el libro, y lo que se descarta se enseña ("Lo que puedes saltarte") para que el estudiante confíe en el recorte. Opcionalmente, los exámenes de años anteriores ajustan las prioridades ("Ha caído en examen").

## Operating Context

- Flujo lineal de tres pasos en una sola ventana: cargar el PDF → confirmar el coste → recibir los dos PDF. El estudiante suele estar estresado y sin tiempo.
- El procesamiento dura minutos (un libro de 300 páginas tarda menos de 15 min). Durante ese tiempo el estudiante mira la barra de progreso, el tiempo restante y el coste acumulado, y puede cancelar y retomar más tarde sin pagar dos veces.
- El estudiante paga la IA con su propia clave de API de Anthropic, así que el coste estimado se muestra antes de procesar, en euros y en dólares.
- Los PDF de salida se leen en pantalla o se imprimen en blanco y negro para subrayarlos y marcarlos a mano.

## Capabilities and Constraints

- Pantallas: asistente de primer arranque (clave de API), Inicio (arrastrar y soltar, capítulos con casillas, nivel de detalle, tipo de examen, estimación), Procesando, Listo (miniaturas, Abrir resumen, Abrir esquema, Mostrar en carpeta), Ajustes y Historial.
- Ventana de 900 × 640 px como mínimo. La interfaz responde siempre en menos de 100 ms: el trabajo pesado corre en un hilo aparte.
- Nunca se muestra un error técnico crudo: cada error tiene un mensaje en lenguaje normal y una acción (Reintentar, Cambiar clave, Elegir otro archivo).
- Interfaz en español, preparada para traducciones (Qt `.ts`).
- Privacidad: sin telemetría ni analíticas. La clave de API se guarda en el llavero del sistema.
- Fuera de alcance en la 1.0: móvil, cuentas de usuario, nube, edición del resumen dentro de la app y formatos que no sean PDF.

## Brand Commitments

- Nombre: **Criba**. Lema implícito: separar el grano de la paja.
- Color de acento obligatorio en el spec: verde trigo `#6B8E23`. Prioridades en los PDF: Alta `#C0392B`, Media `#D68910`, Baja `#7F8C8D`, siempre acompañadas de texto o estrellas.
- Tipografías incluidas en la app y en los PDF: Inter (títulos) y Source Serif 4 (texto).
- Voz: tuteo, cercana y calmada. Como un compañero que ya aprobó: directo, tranquilizador, sin jerga técnica ni exclamaciones.

## Evidence on Hand

Todavía no hay libros reales, capturas, testimonios ni datos de uso. No hay que inventarlos. Los PDF de prueba se generan con scripts propios para no usar material con derechos de autor.

## Product Principles

1. **Confianza por trazabilidad:** todo lo que Criba afirma se puede comprobar en una página concreta del libro.
2. **Calma ante el examen:** la interfaz baja la ansiedad. Un solo camino claro, sin decisiones innecesarias y con buenos valores por defecto.
3. **Sin sorpresas con el dinero:** el coste se ve antes de pagar y nunca se cobra dos veces el mismo trabajo.
4. **Funciona sin instrucciones:** si hace falta explicar algo, se explica en la propia pantalla, en una frase.

## Accessibility & Inclusion

Se puede usar entero con el teclado, con contraste WCAG AA y respetando los tamaños de letra del sistema. Los PDF se imprimen bien en blanco y negro, así que la prioridad nunca se indica solo con color. Las animaciones respetan la preferencia de "reducir movimiento".
