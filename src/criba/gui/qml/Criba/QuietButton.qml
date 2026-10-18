import QtQuick
import QtQuick.Controls.Basic

// Acción secundaria sobre la hoja: borde fino, fondo de papel.
Button {
    id: control

    property bool destructive: false

    implicitHeight: 32
    implicitWidth: contentItem.implicitWidth + 28
    font.family: Theme.sans
    font.pixelSize: Theme.body
    font.weight: Font.Medium
    hoverEnabled: true
    Accessible.name: text

    contentItem: Text {
        text: control.text
        font: control.font
        color: control.destructive ? Theme.danger : Theme.ink
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        radius: 6
        color: control.down ? Theme.hair : control.hovered ? Theme.selection : Theme.field
        border.width: 1
        border.color: control.hovered && !control.destructive ? Theme.accent : Theme.fieldBorder
        opacity: control.enabled ? 1 : 0.45
        Behavior on color { ColorAnimation { duration: Theme.fast } }
        FocusRing { shown: control.visualFocus }
    }
}
