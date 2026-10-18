import QtQuick
import QtQuick.Controls.Basic

// Botón sobre la tapa verde (Historial, Ajustes, Volver).
Button {
    id: control

    property string iconSource: ""

    implicitHeight: 32
    implicitWidth: row.implicitWidth + 24
    font.family: Theme.sans
    font.pixelSize: Theme.body
    font.weight: Font.Medium
    hoverEnabled: true
    Accessible.name: text

    contentItem: Item {
        implicitWidth: row.implicitWidth
        Row {
            id: row
            anchors.centerIn: parent
            spacing: 8
            Image {
                visible: control.iconSource !== ""
                source: control.iconSource
                sourceSize: Qt.size(18, 18)
                width: 18
                height: 18
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                text: control.text
                font: control.font
                color: Theme.coverInk
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }

    background: Rectangle {
        radius: 6
        color: control.down ? Qt.rgba(1, 1, 1, 0.2) : control.hovered ? Qt.rgba(1, 1, 1, 0.12) : "transparent"
        Behavior on color { ColorAnimation { duration: Theme.fast } }
        Rectangle {
            visible: control.visualFocus
            anchors.fill: parent
            anchors.margins: -3
            radius: 9
            color: "transparent"
            border.width: 2
            border.color: Theme.coverInk
        }
    }
}
