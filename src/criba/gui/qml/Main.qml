import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: window
    title: "Criba"
    width: 1040
    height: 720
    minimumWidth: 900
    minimumHeight: 640
    visible: true

    // Paleta provisional; el sistema de diseño completo llega en F4 (Impeccable).
    readonly property bool dark: Application.styleHints.colorScheme === Qt.ColorScheme.Dark
    readonly property color accent: "#6B8E23"
    readonly property color bg: dark ? "#16180F" : "#FAFAF5"
    readonly property color fg: dark ? "#ECEEE4" : "#23261C"
    readonly property color muted: dark ? "#A3A895" : "#5F6553"

    color: bg

    ColumnLayout {
        anchors.centerIn: parent
        spacing: 12

        Label {
            Layout.alignment: Qt.AlignHCenter
            text: "Criba"
            color: window.fg
            font.pixelSize: 40
            font.weight: Font.DemiBold
        }
        Label {
            Layout.alignment: Qt.AlignHCenter
            text: qsTr("Separa el grano de la paja")
            color: window.muted
            font.pixelSize: 16
        }
        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 12
            width: 48
            height: 3
            radius: 2
            color: window.accent
        }
    }
}
