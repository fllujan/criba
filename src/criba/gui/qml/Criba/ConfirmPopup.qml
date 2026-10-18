import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Confirmación de una decisión que cuesta dinero o no se puede deshacer.
Popup {
    id: popup

    property string title: ""
    property string message: ""
    property string confirmText: qsTr("Confirmar")
    property string cancelText: qsTr("Volver")
    property bool destructive: false
    signal confirmed()

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(480, parent ? parent.width - 64 : 480)
    modal: true
    focus: true
    padding: 24
    closePolicy: Popup.CloseOnEscape

    Overlay.modal: Rectangle { color: Theme.scrim }

    enter: Transition {
        NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.base; easing.type: Theme.easing }
        NumberAnimation { property: "y"; from: popup.y + 8; to: popup.y; duration: Theme.base; easing.type: Theme.easing }
    }
    exit: Transition {
        NumberAnimation { property: "opacity"; to: 0; duration: Theme.fast }
    }

    background: Rectangle {
        radius: 12
        color: Theme.paper
        border.width: 1
        border.color: Theme.hair
    }

    contentItem: ColumnLayout {
        spacing: 16
        Text {
            Layout.fillWidth: true
            text: popup.title
            color: Theme.ink
            font.family: Theme.sans
            font.pixelSize: Theme.heading
            font.weight: Font.DemiBold
            wrapMode: Text.WordWrap
            Accessible.role: Accessible.Heading
        }
        Body {
            Layout.fillWidth: true
            text: popup.message
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 8
            spacing: 8
            Item { Layout.fillWidth: true }
            QuietButton {
                text: popup.cancelText
                implicitHeight: 40
                onClicked: popup.close()
            }
            PrimaryButton {
                id: ok
                objectName: "confirmButton"
                text: popup.confirmText
                implicitHeight: 40
                implicitWidth: Math.max(140, contentItem.implicitWidth + 40)
                onClicked: { popup.close(); popup.confirmed() }
            }
        }
    }
    onOpened: ok.forceActiveFocus()
}
