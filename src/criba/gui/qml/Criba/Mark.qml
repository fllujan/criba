import QtQuick
import QtQuick.Shapes

// Marca a bolígrafo en una celda fija del margen.
// state: "off" (casilla vacía), "on" (marcada), "busy" (en curso), "struck" (descartada)
Item {
    id: mark

    property string mode: "off"
    property color color: Theme.pen
    readonly property bool on: mode === "on"

    implicitWidth: 20
    implicitHeight: 20

    Shape {
        width: 20
        height: 20
        anchors.centerIn: parent
        scale: Math.min(mark.width, mark.height) / 20
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            strokeColor: mark.color
            strokeWidth: 1.3
            fillColor: "transparent"
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: "M3.2 3.6 C7 3.1 12.5 3.3 16.6 3.2 C16.9 7.5 16.7 12.4 16.9 16.5 C12 16.9 7.4 16.6 3.4 16.8 C3.1 12.3 3.4 7.8 3.2 3.6Z" }
        }

        ShapePath {
            id: tick
            strokeColor: mark.color
            strokeWidth: 2.1
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            trim.end: mark.on ? 1 : 0
            Behavior on trim.end {
                NumberAnimation { duration: mark.on ? Theme.stroke : 0; easing.type: Easing.OutCubic }
            }
            PathSvg { path: "M5.6 10.4 C6.8 11.3 7.9 12.6 8.7 14.1 C10.6 9.6 13.4 5.6 18.4 1.6" }
        }

        ShapePath {
            strokeColor: mark.mode === "struck" ? mark.color : "transparent"
            strokeWidth: 1.6
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            PathSvg { path: "M4.6 15.2 C8.4 11.6 11.8 8.4 15.6 4.8" }
        }
    }

    // En curso: un punto de tinta que respira (quieto con movimiento reducido).
    Rectangle {
        visible: mark.mode === "busy"
        anchors.centerIn: parent
        width: 6
        height: 6
        radius: 3
        color: mark.color
        SequentialAnimation on opacity {
            running: mark.mode === "busy" && !Theme.reduceMotion
            loops: Animation.Infinite
            NumberAnimation { from: 1; to: 0.25; duration: 700; easing.type: Easing.InOutSine }
            NumberAnimation { from: 0.25; to: 1; duration: 700; easing.type: Easing.InOutSine }
        }
    }
}
