import QtQuick
import QtQuick.Layouts
import "Messages.js" as Msg

// Exámenes antiguos añadidos: una línea del cuaderno por examen, con Quitar.
ColumnLayout {
    id: list

    property var model: []
    property bool locked: false
    readonly property int count: model.length
    signal removeRequested(int index)

    spacing: 0
    Accessible.role: Accessible.List
    Accessible.name: qsTr("Exámenes antiguos")

    Repeater {
        model: list.model
        delegate: Item {
            id: row
            required property var modelData
            required property int index
            Layout.fillWidth: true
            implicitHeight: Theme.row
            Accessible.role: Accessible.ListItem
            Accessible.name: modelData.name + ", " + detail.text

            Rectangle { width: parent.width; height: 1; color: Theme.hair }
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 4
                anchors.rightMargin: 4
                spacing: 12
                Text {
                    Layout.fillWidth: true
                    text: row.modelData.name
                    color: Theme.ink
                    font.family: Theme.serif
                    font.pixelSize: Theme.body
                    elide: Text.ElideMiddle
                }
                Text {
                    id: detail
                    text: row.modelData.scanned > 0
                          ? qsTr("%1 · escaneado").arg(Msg.pageCount(row.modelData.pages))
                          : Msg.pageCount(row.modelData.pages)
                    color: Theme.muted
                    font.family: Theme.sans
                    font.pixelSize: Theme.caption
                    font.features: { "tnum": 1 }
                }
                LinkButton {
                    visible: !list.locked
                    text: qsTr("Quitar")
                    font.pixelSize: Theme.caption
                    Accessible.name: qsTr("Quitar %1").arg(row.modelData.name)
                    onClicked: list.removeRequested(row.index)
                }
            }
        }
    }
    Rectangle {
        Layout.fillWidth: true
        visible: list.count > 0
        implicitHeight: 1
        color: Theme.hair
    }
}
