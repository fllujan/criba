import QtQuick
import QtQuick.Layouts

// Mensaje en la hoja, entre dos filetes: el problema en lenguaje normal y qué puedes hacer.
// Los errores llevan una marca tachada en la celda del margen, como una corrección a boli.
Item {
    id: notice

    property string kind: "error"   // "error" | "info"
    property string text: ""
    property bool marginMark: true  // solo si el aviso está en la columna principal
    property alias actions: actionRow.data
    readonly property color rule: kind === "error" ? Theme.danger : Theme.pen

    implicitHeight: col.implicitHeight + 32
    Accessible.role: Accessible.AlertMessage
    Accessible.name: text

    Rectangle { width: parent.width; height: 1; color: notice.rule; opacity: 0.6 }
    Rectangle { y: parent.height - 1; width: parent.width; height: 1; color: notice.rule; opacity: 0.6 }

    Mark {
        visible: notice.kind === "error" && notice.marginMark
        x: 82 - Theme.contentX
        y: 16
        mode: "struck"
        color: Theme.danger
    }

    ColumnLayout {
        id: col
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
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
