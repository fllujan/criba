import QtQuick

// Barra de progreso: filete de la hoja que se rellena de verde.
Item {
    id: bar

    property real value: 0
    implicitHeight: 6
    Accessible.role: Accessible.ProgressBar
    Accessible.name: qsTr("Progreso")
    Accessible.description: Math.round(value * 100) + " %"

    Rectangle {
        anchors.fill: parent
        radius: height / 2
        color: Theme.hair
    }
    Rectangle {
        height: parent.height
        radius: height / 2
        width: Math.max(height, parent.width * Math.max(0, Math.min(1, bar.value)))
        color: Theme.accent
        Behavior on width { NumberAnimation { duration: Theme.base * 2; easing.type: Theme.easing } }
    }
}
