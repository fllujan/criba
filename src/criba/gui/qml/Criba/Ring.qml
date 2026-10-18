import QtQuick
import QtQuick.Shapes

// Número de sección rodeado a mano en el margen, como los ejercicios del cuaderno.
Item {
    id: ring

    property string number: "1"
    property color color: Theme.pen

    width: 32
    height: 32
    Accessible.ignored: true

    Shape {
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: ring.color
            strokeWidth: 1.3
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            PathSvg { path: "M17.5 4.6 C24.4 4.9 28.2 9.6 27.6 16.4 C27 23.1 21.8 27.4 15.4 27.2 C8.6 27 4.3 22 4.6 15.6 C4.9 9.2 9.7 4.5 16.8 4.9 C18.5 5 19.8 5.6 20.6 6.2" }
        }
    }

    Text {
        anchors.centerIn: parent
        text: ring.number
        color: ring.color
        font.family: Theme.serif
        font.italic: true
        font.weight: Font.Medium
        font.pixelSize: Math.round(16 * Math.min(Theme.scale, 1.25))  // cabe en el anillo de 32 px
    }
}
