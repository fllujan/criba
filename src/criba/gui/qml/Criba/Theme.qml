pragma Singleton
import QtQuick

// Sistema de diseño «Cuaderno de cuadros»: tapa verde, hoja cuadriculada, tinta de bolígrafo.
QtObject {
    id: theme

    property string forced: ""   // "light" | "dark": solo para desarrollo (CRIBA_THEME)
    readonly property bool dark: forced !== "" ? forced === "dark"
                                               : Application.styleHints.colorScheme === Qt.ColorScheme.Dark
    readonly property bool reduceMotion: Application.styleHints.accessibility.motionPreference === Qt.ReducedMotion

    // Color: plano, por regiones. La tapa es la marca; la hoja es el trabajo.
    readonly property color cover: dark ? "#34480F" : "#4E6A17"
    readonly property color coverInk: "#FFFFFF"
    readonly property color coverMuted: dark ? "#D3DCC2" : "#E3EAD5"
    readonly property color label: dark ? "#20251C" : "#FFFFFF"
    readonly property color accent: dark ? "#8FB43C" : "#6B8E23"
    readonly property color accentInk: dark ? "#B9D57A" : "#3F5712"   // texto verde sobre la hoja
    readonly property color paper: dark ? "#161914" : "#FCFDFA"
    readonly property color grid: dark ? "#20261E" : "#E3EBF1"
    readonly property color ink: dark ? "#E7EBE2" : "#1F2420"
    readonly property color muted: dark ? "#A4AD9C" : "#565F55"
    readonly property color hair: dark ? "#2E352B" : "#DCE3DA"
    readonly property color pen: dark ? "#9DB4F5" : "#1F3A8A"           // bolígrafo azul
    readonly property color selection: dark ? "#26301B" : "#EEF3E2"
    readonly property color field: dark ? "#1D211A" : "#FFFFFF"
    readonly property color fieldBorder: dark ? "#4A5441" : "#B9C4B1"
    readonly property color primary: dark ? "#5B7C1D" : "#4E6A17"
    readonly property color primaryHover: dark ? "#668A22" : "#435C12"
    readonly property color danger: dark ? "#F08A7E" : "#A93226"
    readonly property color scrim: dark ? "#99000000" : "#661F2420"

    // Tipografía: las mismas fuentes que los PDF. Respeta el tamaño de letra del sistema.
    readonly property string sans: "Inter"
    readonly property string serif: "Source Serif 4"
    readonly property real scale: Math.max(1, Math.min(1.5, Qt.application.font.pixelSize / 13))
    readonly property int small: Math.round(12 * scale)
    readonly property int caption: Math.round(13 * scale)
    readonly property int body: Math.round(14 * scale)
    readonly property int bodyLarge: Math.round(15 * scale)
    readonly property int heading: Math.round(18 * scale)
    readonly property int title: Math.round(24 * scale)
    readonly property int figure: Math.round(32 * scale)

    // Retícula: todo encaja en celdas de 16 px (4 mm del cuaderno).
    readonly property int cell: 16
    readonly property int row: Math.max(32, Math.round(32 * scale / 8) * 8)
    readonly property int marginX: 112          // filete del margen
    readonly property int contentX: marginX + cell

    // Movimiento: corto, con frenada; nada si el sistema pide reducir movimiento.
    readonly property int fast: reduceMotion ? 0 : 140
    readonly property int base: reduceMotion ? 0 : 220
    readonly property int stroke: reduceMotion ? 0 : 360
    readonly property int easing: Easing.OutExpo
}
