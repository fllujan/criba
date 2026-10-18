import QtQuick
import QtQuick.Controls.Basic

// Campo de texto sobre la hoja.
TextField {
    id: control

    implicitHeight: 36
    leftPadding: 12
    rightPadding: 12
    font.family: Theme.sans
    font.pixelSize: Theme.body
    color: Theme.ink
    placeholderTextColor: Theme.muted
    selectionColor: Theme.accent
    selectedTextColor: Theme.coverInk
    selectByMouse: true

    background: Rectangle {
        radius: 6
        color: Theme.field
        border.width: control.activeFocus ? 2 : 1
        border.color: control.activeFocus ? Theme.pen : Theme.fieldBorder
    }
}
