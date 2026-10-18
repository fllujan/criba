---
name: Criba
description: Cuaderno de cuadros para separar el grano de la paja de un libro en PDF.
colors:
  cover: "#4E6A17"
  cover-dark: "#34480F"
  cover-ink: "#FFFFFF"
  cover-muted: "#E3EAD5"
  cover-muted-dark: "#D3DCC2"
  label: "#FFFFFF"
  label-dark: "#20251C"
  accent: "#6B8E23"
  accent-dark: "#8FB43C"
  accent-ink: "#3F5712"
  accent-ink-dark: "#B9D57A"
  primary: "#4E6A17"
  primary-hover: "#435C12"
  primary-dark: "#5B7C1D"
  primary-hover-dark: "#668A22"
  pen: "#1F3A8A"
  pen-dark: "#9DB4F5"
  paper: "#FCFDFA"
  paper-dark: "#161914"
  grid: "#E3EBF1"
  grid-dark: "#20261E"
  ink: "#1F2420"
  ink-dark: "#E7EBE2"
  muted: "#565F55"
  muted-dark: "#A4AD9C"
  hair: "#DCE3DA"
  hair-dark: "#2E352B"
  selection: "#EEF3E2"
  selection-dark: "#26301B"
  field: "#FFFFFF"
  field-dark: "#1D211A"
  field-border: "#B9C4B1"
  field-border-dark: "#4A5441"
  danger: "#A93226"
  danger-dark: "#F08A7E"
typography:
  figure:
    fontFamily: "Inter"
    fontSize: "32px"
    fontWeight: 600
    letterSpacing: "-0.6px"
  title:
    fontFamily: "Inter"
    fontSize: "24px"
    fontWeight: 600
    letterSpacing: "-0.4px"
  heading:
    fontFamily: "Inter"
    fontSize: "18px"
    fontWeight: 600
    letterSpacing: "-0.2px"
  body-large:
    fontFamily: "Inter"
    fontSize: "15px"
    fontWeight: 500
  body:
    fontFamily: "Inter"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.3
  caption:
    fontFamily: "Inter"
    fontSize: "13px"
    fontWeight: 400
  small:
    fontFamily: "Inter"
    fontSize: "12px"
    fontWeight: 700
    letterSpacing: "0.3px"
  book:
    fontFamily: "Source Serif 4"
    fontSize: "15px"
    fontWeight: 400
  margin-note:
    fontFamily: "Source Serif 4"
    fontSize: "12px"
    fontWeight: 400
    fontFeature: "\"tnum\" 1"
  ring-numeral:
    fontFamily: "Source Serif 4"
    fontSize: "16px"
    fontWeight: 500
rounded:
  segment: "5px"
  control: "6px"
  button: "8px"
  label: "10px"
  sheet: "12px"
  pill: "9999px"
spacing:
  gap-tight: "8px"
  gap: "12px"
  cell: "16px"
  cover-pad: "24px"
  row: "32px"
  margin: "112px"
  content-x: "128px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.cover-ink}"
    typography: "{typography.body-large}"
    rounded: "{rounded.button}"
    height: "48px"
    padding: "0 24px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  button-quiet:
    backgroundColor: "{colors.field}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    height: "32px"
    padding: "0 14px"
  button-quiet-hover:
    backgroundColor: "{colors.selection}"
  button-quiet-destructive:
    textColor: "{colors.danger}"
  button-cover:
    textColor: "{colors.cover-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    height: "32px"
    padding: "0 12px"
  link:
    textColor: "{colors.accent-ink}"
    typography: "{typography.body}"
    height: "24px"
  field:
    backgroundColor: "{colors.field}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    height: "36px"
    padding: "0 12px"
  segmented:
    backgroundColor: "{colors.field}"
    rounded: "{rounded.button}"
    height: "38px"
    padding: "3px"
  segmented-option-selected:
    backgroundColor: "{colors.selection}"
    textColor: "{colors.accent-ink}"
    rounded: "{rounded.segment}"
  cover-bar:
    backgroundColor: "{colors.cover}"
    textColor: "{colors.cover-ink}"
    height: "80px"
    padding: "0 24px"
  cover-label:
    backgroundColor: "{colors.label}"
    textColor: "{colors.ink}"
    rounded: "{rounded.label}"
    height: "52px"
    padding: "0 16px"
  chapter-row:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.book}"
    height: "{spacing.row}"
  chapter-row-hover:
    backgroundColor: "{colors.selection}"
  confirm-sheet:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sheet}"
    padding: "24px"
    width: "480px"
  ink-bar:
    backgroundColor: "{colors.hair}"
    rounded: "{rounded.pill}"
    height: "6px"
---

# Design System: Criba

## Overview

**Creative North Star: "El cuaderno de la asignatura"**

Criba es un cuaderno de cuadros abierto sobre la mesa. Arriba, la tapa de polipropileno verde con su etiqueta blanca, donde se escribe la asignatura. Debajo, la hoja: cuadrícula de 16 px muy tenue, filete de margen verde y, en el margen, marcas a bolígrafo azul en celdas fijas que dicen qué entra, qué está en curso y qué está hecho. La interfaz no flota sobre la hoja: se escribe en ella.

El color va por regiones planas. La tapa es la marca y el único bloque de color fuerte; la hoja es el trabajo y se mantiene casi blanca (o pizarra en modo oscuro, con la misma geometría). La densidad es la de una web de estudio: filas de 32 px separadas por filetes de 1 px, sin tarjetas, sin degradados y sin sombras. La retícula no es un fondo decorativo: los valores de layout se alinean con la celda de 16 px.

Dos voces tipográficas separan lo que dice Criba de lo que viene del libro: Inter para la interfaz y Source Serif 4 para los títulos de capítulo y las anotaciones del margen. El movimiento es corto y con frenada; el único gesto con duración propia es el trazo de la marca al completarse, y desaparece si el sistema pide reducir movimiento.

**Key Characteristics:**
- Tapa verde plana a ancho completo (80 px) con etiqueta blanca redondeada.
- Hoja cuadriculada de 16 px con filete de margen verde a 112 px.
- El margen es una columna de estado: marcas y números rodeados a bolígrafo.
- Filetes de 1 px en lugar de tarjetas; profundidad cero.
- Inter para la interfaz, Source Serif 4 para el libro.
- Modo oscuro automático con la misma geometría.

## Colors

Paleta plana por regiones: un verde de tapa saturado, una hoja casi neutra con cuadrícula fría y un azul de bolígrafo que solo aparece como tinta. Cada token tiene pareja clara/oscura (sufijo `-dark`) y se resuelve en `Theme.qml` según el esquema del sistema.

### Primary
- **Verde Tapa** (cover / cover-dark): fondo de la barra-tapa a ancho completo. Es la región de marca; nada más en la pantalla ocupa tanta superficie verde.
- **Verde Tapa Acción** (primary / primary-dark, hover primary-hover / primary-hover-dark): fondo del botón principal. En claro coincide con la tapa a propósito: el botón es un trozo de tapa sobre la hoja. Al pulsar se oscurece un 15 % más.
- **Verde Trigo** (accent / accent-dark): el acento obligatorio de la marca. Filete del margen (2 px, opacidad 0,85), relleno de la barra de progreso, borde de la opción seleccionada, borde de hover de los botones discretos, color de selección de texto.
- **Verde Trigo Tinta** (accent-ink / accent-ink-dark): verde legible como texto sobre la hoja: enlaces, opción seleccionada, título pequeño de la etiqueta.

### Secondary
- **Bolígrafo Azul** (pen / pen-dark): tinta de bolígrafo. Marcas y números rodeados del margen, páginas anotadas, anillo de foco, borde del campo con foco, raya de la etiqueta al editar, avisos informativos.

### Neutral
- **Hoja** (paper / paper-dark): fondo de la ventana y de las zonas lisas sobre la cuadrícula (columna derecha, filas, hoja de confirmación).
- **Cuadrícula** (grid / grid-dark): líneas de 1 px de la retícula de 16 px.
- **Tinta** (ink / ink-dark): texto principal.
- **Lápiz** (muted / muted-dark): texto secundario, conteos, capítulos excluidos, marcadores de posición.
- **Filete** (hair / hair-dark): filetes entre filas, pista de la barra de progreso, borde de la hoja de confirmación.
- **Selección** (selection / selection-dark): fondo de fila resaltada, opción elegida y hover suave (al 50–60 % de opacidad).
- **Campo** (field / field-dark) y **Borde de campo** (field-border / field-border-dark): fondo y borde de controles sobre la hoja.
- **Sobre la tapa** (cover-ink, cover-muted / cover-muted-dark): texto blanco y pasos no actuales sobre el verde.
- **Etiqueta** (label / label-dark): fondo de la etiqueta de la tapa.
- **Corrección** (danger / danger-dark): texto de error, filetes del aviso de error y marca tachada del margen.

### Named Rules
**The Tapa y Hoja Rule.** El verde saturado vive en la tapa y en el botón principal. La hoja no lleva fondos de color: el verde entra en ella solo como filete, borde, relleno de progreso o texto.

**The Bolígrafo Rule.** El azul `pen` es tinta, nunca superficie. Se usa para marcas, anotaciones del margen y foco; no para fondos ni botones.

## Typography

**Display Font:** Inter (incluida en la app)
**Body Font:** Inter
**Book Font:** Source Serif 4 (incluida en la app)

**Character:** Inter, neutra y densa, es la voz de Criba; Source Serif 4 marca todo lo que procede del libro (títulos de capítulo) y las anotaciones a mano del margen, en cursiva.

Todos los tamaños se multiplican por `Theme.scale` = tamaño de letra del sistema / 13, limitado a 1–1,5, y se redondean. Los valores de abajo son la base a escala 1.

### Hierarchy
- **Figure** (600, 32 px, −0,6): la cifra del coste estimado y del gasto acumulado. Una por pantalla.
- **Title** (600, 24 px, −0,4): titular de cada pantalla («Analizando el libro», «Ya tienes tus dos PDF»).
- **Heading** (600, 18 px, −0,2): encabezados de bloque junto a su número rodeado; título de la hoja de confirmación.
- **Body Large** (500, 15 px): texto de la etiqueta de la tapa, botón principal, segundo dato junto a la cifra.
- **Body** (400, 14 px, interlineado 1,3): texto corrido, botones secundarios, opciones. Nombres de control en 600.
- **Caption** (13 px): detalle a la derecha del encabezado, conteos de páginas, ayudas; en 600 nombra un control o un dato («Nivel de detalle», «Tiempo restante»).
- **Small** (700, 12 px, +0,3): título de la etiqueta («Asignatura») y números de los pasos; en peso normal, pistas de las opciones.
- **Book** (Source Serif 4, 400, 15 px): títulos de capítulo en las filas.
- **Margin Note** (Source Serif 4 cursiva, 12 px, cifras tabulares): páginas a bolígrafo en el margen.
- **Ring Numeral** (Source Serif 4 cursiva, 500, 16 px): número de sección rodeado.

### Named Rules
**The Dos Voces Rule.** La serif solo aparece para lo que viene del libro o lo que se anota a mano. La interfaz habla siempre en Inter.

**The Tamaño del Sistema Rule.** Ningún texto de interfaz usa un tamaño fijo: siempre un rol de `Theme`, que respeta el tamaño de letra del sistema.

## Layout

Ventana mínima de 900 × 640 px; por defecto 1200 × 780. La tapa ocupa los 80 px superiores con 24 px de relleno lateral y 24 px entre grupos: etiqueta a la izquierda (hasta 400 px o el 36 % del ancho; 30 % por debajo de 1000 px), pasos 1 Libro · 2 Procesar · 3 Listo en el centro (28 px entre pasos; 16 px y solo el nombre del paso actual por debajo de 1000 px) e Historial y Ajustes a la derecha.

La hoja ocupa el resto. La retícula de 16 px se dibuja a ancho y alto completos; el filete de margen está en x = 112 px y el contenido empieza en 128 px (margen + una celda). En el margen, las páginas anotadas ocupan 72 px alineadas a la derecha y la marca está en x = 82. Los números rodeados quedan a la izquierda del bloque, a −44/−48 px.

Pantallas con decisión (Inicio, Procesando) tienen dos columnas: la principal desde 128 px y una columna derecha de 300–400 px (30 % del ancho) a 32 px del borde. La columna derecha es un parche liso de hoja sin cuadrícula, 16 px más ancho por cada lado. El ritmo vertical es la fila de 32 px (crece en pasos de 8 px con la escala del sistema), con huecos de 8, 12, 16 y 24 px.

Ajustes e Historial entran como una hoja nueva que se desliza desde la derecha (`base`), y las pantallas del flujo cambian por fundido (`base`).

**The Celda Rule.** Las medidas de layout son múltiplos de 8 y, en lo estructural, de la celda de 16 px. La retícula es estructura, no textura.

## Elevation & Depth

Sistema plano. No hay sombras en ningún componente: la jerarquía se construye con regiones de color (tapa frente a hoja), parches lisos de hoja sobre la cuadrícula y filetes de 1 px. La única capa elevada es la hoja de confirmación modal, que se separa con un velo (`#661F2420` en claro, `#99000000` en oscuro) y un borde `hair` de 1 px, no con sombra.

**The Sin Sombra Rule.** Ninguna superficie proyecta sombra. Si algo necesita separarse, usa un filete, un parche liso de hoja o el velo modal.

## Shapes

Esquinas suaves en los controles y rectas en la hoja. La etiqueta de la tapa es lo más redondeado de la superficie fija (10 px), como una etiqueta adhesiva; los botones principales y el control segmentado van a 8 px; campos, botones discretos y botones de tapa a 6 px; las opciones internas del segmentado a 5 px; la hoja de confirmación a 12 px. Las filas, la columna derecha y las miniaturas de PDF son rectas. La barra de progreso y los círculos de paso son píldoras.

Las formas dibujadas a mano (casilla de la marca, visto, tachado, anillo del número) son trazos SVG irregulares con extremos redondeados (1,3 px el contorno, 2,1 px el visto), nunca formas geométricas perfectas. La raya discontinua de la etiqueta (trazos de 3 px cada 6 px) indica dónde se escribe.

## Components

### Buttons
- **Shape:** esquinas de 8 px en el principal; 6 px en el resto.
- **Primary:** verde tapa con texto blanco en Inter 700 a 15 px, 48 px de alto, mínimo 160 px de ancho o el texto + 48 px. En la columna derecha ocupa todo el ancho. Se usa para la acción que decide la pantalla («Generar resumen y esquema»). Deshabilitado al 45 % de opacidad.
- **Hover / Focus:** el color cambia en `fast` (140 ms) a `primary-hover`; al pulsar, 15 % más oscuro. El foco de teclado es el anillo de bolígrafo: 2 px `pen`, separado 3 px.
- **Quiet:** fondo `field`, borde 1 px `field-border`, texto `ink` en 500 a 14 px, 32 px de alto (40 px en la hoja de confirmación). Hover: fondo `selection` y borde `accent`. Variante destructiva con texto `danger` y sin borde verde.
- **Cover:** sobre la tapa, transparente con texto blanco e icono SVG de 18 px opcional; hover blanco al 12 %, pulsado al 20 %. El foco es un anillo blanco de 2 px, para que se vea sobre el verde.
- **Link:** texto `accent-ink` en 500 con subrayado de 1 px al 45 % que pasa al 100 % en hover. Para acciones secundarias («Marcar todos», «Elegir un rango de páginas»).

### Segmented
- **Style:** marco `field` con borde `field-border`, 8 px de esquina y 3 px de relleno; 38 px de alto o 50 px si las opciones llevan pista.
- **State:** la opción elegida tiene fondo `selection`, borde de 2 px `accent` y texto `accent-ink` en 700; las demás, transparentes con hover de `selection` al 60 %. Se recorre con las flechas; el foco rodea todo el marco.

### Inputs / Fields
- **Style:** fondo `field`, borde 1 px `field-border`, 6 px de esquina, 36 px de alto, 12 px de relleno lateral.
- **Focus:** el borde pasa a 2 px `pen`, como si se escribiera con bolígrafo.
- **Etiqueta de la tapa:** campo sin caja sobre la etiqueta blanca, con raya discontinua `field-border` que pasa a `pen` y 2 px al editar. Sin foco muestra el nombre entero con «…».

### Navigation
- **Pasos:** círculo de 22 px con número en Small; actual y pasados en blanco relleno con número verde tapa, futuros con contorno `cover-muted`. El nombre del paso actual va en 700 blanco; los demás en 500 `cover-muted`.
- **Historial / Ajustes:** botones de tapa con icono, siempre visibles salvo en el asistente; en Ajustes e Historial se sustituyen por «Volver».

### Chapter Row
- **Style:** fila de 32 px con filete superior `hair`. En el margen, las páginas a bolígrafo en cursiva y la marca; en la hoja, el título en Source Serif 4 y el número de páginas en Caption `muted`.
- **State:** excluido o tachado, título en `muted` y páginas al 55 %. Hover con `selection` al 55 %; fila resaltada con `selection` y anillo de foco sin hueco. Toda la fila conmuta el capítulo.

### Mark (firma)
La marca a bolígrafo en una celda fija del margen (20 × 20 px, `pen`). Cuatro modos: `off` casilla vacía (pendiente o fuera), `on` visto (incluido o hecho), `busy` punto de 6 px que respira entre opacidad 1 y 0,25 cada 700 ms (en curso), `struck` casilla tachada (descartado; en `danger` para errores). El visto se traza con `trim` en `stroke` (360 ms, OutCubic) al marcarse y aparece al instante al desmarcarse o con movimiento reducido; el punto deja de respirar con movimiento reducido.

### Ring
Número de sección rodeado a mano (32 × 32 px, `pen`, numeral en serif cursiva) en el margen, a la izquierda de cada encabezado de bloque.

### Notice
Aviso entre dos filetes de 1 px (`danger` o `pen`, al 60 %) con el problema en Body 500 y una fila de acciones (QuietButton) debajo. Los errores en la columna principal llevan una marca tachada `danger` en la celda del margen.

### Ink Bar
Barra de progreso de 6 px en píldora: pista `hair`, relleno `accent` que avanza en `base × 2` (440 ms, OutExpo).

### Confirm Sheet
Hoja modal de 480 px como máximo, fondo `paper`, borde `hair`, 12 px de esquina, 24 px de relleno. Título en Heading, mensaje en Body y botones alineados a la derecha (discreto «Volver» y principal de 40 px). Entra con fundido y 8 px de subida en `base`; sale con fundido en `fast`. El foco empieza en el botón de confirmar.

## Do's and Don'ts

### Do:
- **Do** toma todos los colores, tamaños, celdas y duraciones de `Theme`; cada color tiene su pareja oscura y se resuelve solo.
- **Do** pon el estado en el margen con `Mark` en su celda fija (x = 82) y los bloques numerados con `Ring`.
- **Do** separa filas y bloques con filetes de 1 px `hair` y zonas de lectura con parches lisos de `paper` sobre la cuadrícula.
- **Do** usa Source Serif 4 para títulos que vienen del libro y para anotaciones del margen; Inter para todo lo demás.
- **Do** usa una sola acción principal (PrimaryButton) por decisión, y QuietButton o LinkButton para lo secundario.
- **Do** usa las duraciones `fast` (140 ms), `base` (220 ms) y `stroke` (360 ms) con OutExpo; valen 0 con movimiento reducido.
- **Do** muestra el foco de teclado con `FocusRing` (2 px `pen`) en la hoja y con anillo blanco en la tapa.

### Don't:
- **Don't** uses sombras, degradados ni tarjetas flotantes con borde y sombra; la profundidad es cero.
- **Don't** pintes fondos verdes o azules en la hoja: el verde saturado es de la tapa y del botón principal, y el azul es tinta.
- **Don't** construyas una barra lateral gris ni un panel de resumen en tarjeta; el margen y la columna derecha sobre la hoja cumplen ese papel.
- **Don't** fijes tamaños de letra en píxeles en la interfaz; usa los roles de `Theme`, que siguen la escala del sistema.
- **Don't** dibujes las marcas del margen con formas geométricas perfectas o iconos de casilla del sistema; son trazos a mano de `Mark`.
- **Don't** pongas animaciones que bloqueen la interfaz o que ignoren `Theme.reduceMotion`.
