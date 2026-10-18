import QtQuick
import QtQuick.Controls.Basic
import "Messages.js" as Msg

// Fila de capítulo: páginas anotadas y marca en el margen; título del libro en la hoja.
AbstractButton {
    id: row

    required property int index
    required property string title
    required property int firstPage
    required property int lastPage
    required property bool included
    property string markMode: included ? "on" : "off"   // la pantalla Procesando lo cambia
    property bool interactive: true
    property bool highlighted: false
    signal includeToggled(bool included)

    implicitHeight: Theme.row
    hoverEnabled: interactive
    focusPolicy: Qt.NoFocus
    enabled: true
    Accessible.role: interactive ? Accessible.CheckBox : Accessible.ListItem
    Accessible.name: title + ", " + Msg.pages(firstPage, lastPage)
    Accessible.checkable: interactive
    Accessible.checked: included
    onClicked: if (interactive) includeToggled(!included)

    // Margen: páginas a bolígrafo
    Text {
        x: 0
        width: 72
        anchors.verticalCenter: parent.verticalCenter
        horizontalAlignment: Text.AlignRight
        text: Msg.pages(row.firstPage, row.lastPage)
        color: Theme.pen
        opacity: row.markMode === "off" ? 0.55 : 1
        font.family: Theme.serif
        font.italic: true
        font.pixelSize: Theme.small
        font.features: { "tnum": 1 }
    }
    Mark {
        x: 82
        anchors.verticalCenter: parent.verticalCenter
        mode: row.markMode
    }

    // Hoja: título y extensión, con filete inferior
    Rectangle {
        x: Theme.contentX
        width: parent.width - Theme.contentX
        height: parent.height
        color: row.highlighted ? Theme.selection
             : row.hovered ? Qt.rgba(Theme.selection.r, Theme.selection.g, Theme.selection.b, 0.55)
             : Theme.paper
        Behavior on color { ColorAnimation { duration: Theme.fast } }

        Text {
            anchors.left: parent.left
            anchors.leftMargin: 4
            anchors.right: count.left
            anchors.rightMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            text: row.title
            color: row.markMode === "off" || row.markMode === "struck" ? Theme.muted : Theme.ink
            font.family: Theme.serif
            font.pixelSize: Theme.bodyLarge
            elide: Text.ElideRight
        }
        Text {
            id: count
            anchors.right: parent.right
            anchors.rightMargin: 4
            anchors.verticalCenter: parent.verticalCenter
            text: Msg.pageCount(row.lastPage - row.firstPage + 1)
            color: Theme.muted
            font.family: Theme.sans
            font.pixelSize: Theme.caption
            font.features: { "tnum": 1 }
        }
        Rectangle {
            anchors.top: parent.top
            width: parent.width
            height: 1
            color: Theme.hair
        }
    }
    HoverHandler { cursorShape: row.interactive ? Qt.PointingHandCursor : Qt.ArrowCursor }
}
