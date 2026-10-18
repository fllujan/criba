import QtQuick

// La hoja: cuadrícula de 16 px y filete de margen. Se dibuja una vez por tamaño.
Item {
    id: paper

    property int marginX: Theme.marginX
    property bool showRule: true

    Rectangle {
        anchors.fill: parent
        color: Theme.paper
    }

    Canvas {
        id: grid
        anchors.fill: parent
        renderStrategy: Canvas.Cooperative
        onPaint: {
            const ctx = getContext("2d")
            ctx.reset()
            ctx.strokeStyle = Theme.grid
            ctx.lineWidth = 1
            ctx.beginPath()
            for (let x = 0.5; x < width; x += Theme.cell) {
                ctx.moveTo(x, 0)
                ctx.lineTo(x, height)
            }
            for (let y = 0.5; y < height; y += Theme.cell) {
                ctx.moveTo(0, y)
                ctx.lineTo(width, y)
            }
            ctx.stroke()
        }
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        Connections {
            target: Theme
            function onDarkChanged() { grid.requestPaint() }
        }
    }

    Rectangle {
        visible: paper.showRule
        x: paper.marginX - 1
        width: 2
        height: parent.height
        color: Theme.accent
        opacity: 0.85
    }
}
