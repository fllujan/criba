import QtQuick
import QtQuick.Controls.Basic

// Enlace de texto: para acciones secundarias que no merecen un botón.
AbstractButton {
    id: control

    implicitWidth: label.implicitWidth
    implicitHeight: Math.max(24, label.implicitHeight)
    font.family: Theme.sans
    font.pixelSize: Theme.body
    font.weight: Font.Medium
    hoverEnabled: true
    Accessible.role: Accessible.Link
    Accessible.name: text

    contentItem: Text {
        id: label
        text: control.text
        font: control.font
        color: Theme.accentInk
        verticalAlignment: Text.AlignVCenter
        opacity: control.enabled ? 1 : 0.45
    }

    background: Item {
        Rectangle {
            y: label.y + label.height / 2 + label.font.pixelSize / 2 + 2
            width: label.implicitWidth
            height: 1
            color: Theme.accentInk
            opacity: control.hovered ? 1 : 0.45
        }
        FocusRing { target: label; shown: control.visualFocus; gap: 4 }
    }
    HoverHandler { cursorShape: Qt.PointingHandCursor }
}
