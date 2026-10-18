import QtQuick
import QtQuick.Layouts

// Mensaje en la hoja: el problema en lenguaje normal y lo que puedes hacer.
Rectangle {
    id: notice

    property string kind: "error"   // "error" | "info"
    property string text: ""
    property alias actions: actionRow.data

    implicitHeight: col.implicitHeight + 32
    radius: 8
    color: kind === "error" ? Theme.dangerTint : Theme.infoTint
    border.width: 1
    border.color: kind === "error" ? Qt.rgba(Theme.danger.r, Theme.danger.g, Theme.danger.b, 0.35)
                                   : Qt.rgba(Theme.pen.r, Theme.pen.g, Theme.pen.b, 0.3)
    Accessible.role: Accessible.AlertMessage
    Accessible.name: text

    ColumnLayout {
        id: col
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12
        Body {
            Layout.fillWidth: true
            text: notice.text
            color: notice.kind === "error" ? Theme.danger : Theme.ink
            font.weight: Font.Medium
        }
        Flow {
            id: actionRow
            Layout.fillWidth: true
            spacing: 8
            visible: children.length > 0
        }
    }
}
