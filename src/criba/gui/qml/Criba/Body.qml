import QtQuick

// Texto corrido de la interfaz.
Text {
    property bool secondary: false

    color: secondary ? Theme.muted : Theme.ink
    font.family: Theme.sans
    font.pixelSize: Theme.body
    lineHeight: 1.3
    wrapMode: Text.WordWrap
    textFormat: Text.PlainText
}
