import QtQuick

// Anillo de foco de teclado, en tinta de bolígrafo.
Rectangle {
    property Item target: parent
    property bool shown: false
    property real gap: 3

    x: -gap
    y: -gap
    width: target.width + 2 * gap
    height: target.height + 2 * gap
    radius: (target.radius !== undefined ? target.radius : 6) + gap
    color: "transparent"
    border.width: 2
    border.color: Theme.pen
    visible: shown
}
