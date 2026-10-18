# Brief común de los bocetos (no se publica)

Producto: **Criba**, app de escritorio (macOS y Windows, Qt Quick) que convierte un libro de texto en PDF en dos PDF de estudio: «Resumen para estudiar» y «Esquema de examen», usando la IA de Claude con la clave del propio estudiante. Usuario: estudiante español (bachillerato, FP, universidad, oposiciones), sin conocimientos técnicos, con prisa y algo de estrés antes de un examen. Voz: tuteo, cercana, calmada, sin exclamaciones ni jerga.

Pantalla a bocetar: **Inicio con un libro ya cargado** (el momento de decidir y confirmar). Es una herramienta (modo Operate): la navegación y los controles son los estándar de una app de escritorio (botones, casillas, control segmentado, campo de texto). El mundo visual solo aporta tipografía, paleta, densidad y UN gesto distintivo.

Marco: archivo HTML autocontenido de 1440 × 900, `html,body{margin:0;width:1440px;height:900px;overflow:hidden}`, CSS en línea, sin JavaScript, nada externo salvo Google Fonts (Inter y Source Serif 4 están permitidas: son las fuentes de la marca). Menos de 200 líneas. Todo el texto en español.

Restricciones de marca: acento verde trigo `#6B8E23` (el botón principal y lo seleccionado). Prioridad Alta `#C0392B`, Media `#D68910`, Baja `#7F8C8D`, siempre con texto además del color. Contraste WCAG AA (texto blanco sobre #6B8E23 NO llega a AA en tamaños pequeños: usa un verde más oscuro como #4E6A17 si pones texto blanco pequeño encima, o texto grande/negrita).

Contenido real (sintético, coherente):
- Barra de la app: «Criba»; pasos «1 Libro · 2 Procesar · 3 Listo» (estamos en el 1); a la derecha, accesos «Historial» y «Ajustes» (icono de engranaje).
- Archivo: «Biologia_Geologia_1Bach.pdf» · 312 páginas · 4 escaneadas (se leerán con la IA) · botón secundario «Cambiar libro».
- Campo «Asignatura»: «Biología y Geología 1.º Bachillerato».
- Capítulos detectados (casillas, todos marcados salvo «Preliminares»), con páginas del libro:
  - Preliminares · pp. 1–7 (desmarcado)
  - 1. La organización de los seres vivos · pp. 8–27
  - 2. La célula, unidad de vida · pp. 28–51
  - 3. Los tejidos animales y vegetales · pp. 52–71
  - 4. La clasificación de los seres vivos · pp. 72–93
  - 5. Las plantas: nutrición · pp. 94–119
  - 6. Las plantas: relación y reproducción · pp. 120–143
  - 7. Los animales: nutrición · pp. 144–171
  - 8. Los animales: relación · pp. 172–199
  - 9. Los animales: reproducción · pp. 200–223
  - 10. Estructura de la Tierra · pp. 224–251
  - (y 3 más, con «Ver todos» o una lista con scroll)
  - Enlace «Elegir un rango de páginas»
- «Nivel de detalle»: control segmentado Esencial (≈10 %) · **Normal (≈15 %)** · Completo (≈20 %).
- «Tipo de examen»: Test · Desarrollo · **Mixto**.
- Enlace secundario «Añadir exámenes antiguos (opcional)».
- Estimación (se actualiza al cambiar opciones): «305 páginas · unas 96 llamadas a la IA · unos 12 minutos» y coste «≈ 2,10 € (2,28 $)», con una frase: «Solo pagas lo que proceses. Si cancelas, lo hecho se guarda.»
- Botón principal: «Generar» (o «Generar resumen y esquema»).

Calidad: nivel de la mejor app de su categoría: retícula alineada, espaciado consistente, escala tipográfica real, jerarquía clara. Nada de degradados decorativos, glassmorphism, iconos genéricos en baldosas, ni tarjetas anidadas. Etiquetas y textos de 13–15 px como en una app de escritorio; el título más grande no supera ~32 px salvo que la dirección lo pida.
