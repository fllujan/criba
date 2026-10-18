import QtQuick

// Encabezado de bloque con su número rodeado en el margen (x negativa respecto al bloque).
Item {
    id: head

    property string number: ""
    property string title: ""
    property string detail: ""
    property int ringOffset: -48

    implicitHeight: Theme.row
    Accessible.role: Accessible.Heading
    Accessible.name: title

    Ring {
        visible: head.number !== ""
        number: head.number
        x: head.ringOffset
        anchors.verticalCenter: parent.verticalCenter
    }
    Text {
        id: titleText
        anchors.verticalCenter: parent.verticalCenter
        text: head.title
        color: Theme.ink
        font.family: Theme.sans
        font.pixelSize: Theme.heading
        font.weight: Font.DemiBold
        font.letterSpacing: -0.2
    }
    Text {
        anchors.right: parent.right
        anchors.baseline: titleText.baseline
        text: head.detail
        color: Theme.muted
        font.family: Theme.sans
        font.pixelSize: Theme.caption
    }
}
