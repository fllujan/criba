import QtQuick
import QtQuick.Controls.Basic

// Acción principal de la pantalla (una sola): verde de la tapa, texto blanco en negrita.
Button {
    id: control

    implicitHeight: 48
    implicitWidth: Math.max(160, contentItem.implicitWidth + 48)
    font.family: Theme.sans
    font.pixelSize: Theme.bodyLarge
    font.weight: Font.Bold
    hoverEnabled: true
    Accessible.name: text

    contentItem: Text {
        text: control.text
        font: control.font
        color: Theme.coverInk
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        radius: 8
        color: control.down ? Qt.darker(Theme.primary, 1.15)
             : control.hovered ? Theme.primaryHover : Theme.primary
        opacity: control.enabled ? 1 : 0.45
        Behavior on color { ColorAnimation { duration: Theme.fast } }
        FocusRing { shown: control.visualFocus }
    }
}
