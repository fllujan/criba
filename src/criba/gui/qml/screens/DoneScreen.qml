import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Criba
import "../Criba/Messages.js" as Msg

// Listo: las dos hojas con su miniatura, abrirlas y procesar otro libro.
Item {
    id: screen

    required property var backend
    property bool active: false

    component Sheet: ColumnLayout {
        id: sheet
        property string path: ""
        property string caption: ""
        property string openText: ""
        property bool primary: false   // una sola acción principal por pantalla
        spacing: 12

        AbstractButton {
            id: thumbButton
            Layout.preferredWidth: thumbWidth
            Layout.preferredHeight: Math.round(thumbWidth * 1.414)
            hoverEnabled: true
            Accessible.name: sheet.openText
            onClicked: backend.openFile(sheet.path)

            background: Rectangle {
                color: "#FFFFFF"
                border.width: 1
                border.color: thumbButton.hovered ? Theme.accent : Theme.hair
                Behavior on border.color { ColorAnimation { duration: Theme.fast } }
                FocusRing { shown: thumbButton.visualFocus }
            }
            contentItem: Image {
                source: sheet.path ? "image://thumb/" + encodeURIComponent(sheet.path) + "?" + backend.resultCostEur : ""
                sourceSize.width: thumbWidth * 2
                fillMode: Image.PreserveAspectFit
                asynchronous: true
                cache: false
                opacity: status === Image.Ready ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: Theme.base } }
            }
            HoverHandler { cursorShape: Qt.PointingHandCursor }
        }
        Text {
            Layout.preferredWidth: thumbWidth
            text: sheet.caption
            color: Theme.ink
            font.family: Theme.sans
            font.pixelSize: Theme.body
            font.weight: Font.DemiBold
            elide: Text.ElideRight
        }
        PrimaryButton {
            visible: sheet.primary
            Layout.preferredWidth: thumbWidth
            implicitHeight: 44
            text: sheet.openText
            onClicked: backend.openFile(sheet.path)
        }
        QuietButton {
            visible: !sheet.primary
            Layout.preferredWidth: thumbWidth
            implicitHeight: 44
            text: sheet.openText
            onClicked: backend.openFile(sheet.path)
        }
    }

    readonly property int thumbWidth: Math.max(120, Math.min(260, (width - Theme.contentX - 96) / 3, (height - 310) / 1.414))

    Flickable {
        anchors.fill: parent
        contentHeight: column.implicitHeight + 72
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {}

        ColumnLayout {
            id: column
            x: Theme.contentX
            y: 32
            width: screen.width - Theme.contentX - 48
            spacing: 0

            Item {
                implicitWidth: doneTitle.implicitWidth
                implicitHeight: doneTitle.implicitHeight
                // La marca final, en su celda del margen: se dibuja de un trazo al llegar.
                Mark {
                    x: 82 - Theme.contentX
                    anchors.verticalCenter: parent.verticalCenter
                    mode: screen.active ? "on" : "off"
                }
                Text {
                    id: doneTitle
                    text: qsTr("Ya tienes tus dos PDF")
                    color: Theme.ink
                    font.family: Theme.sans
                    font.pixelSize: Theme.title
                    font.weight: Font.DemiBold
                    font.letterSpacing: -0.4
                    Accessible.role: Accessible.Heading
                }
            }
            Body {
                Layout.fillWidth: true
                Layout.topMargin: 8
                secondary: true
                text: backend.resultCostEur > 0
                      ? qsTr("Coste real: %1. Cada idea lleva la página del libro de la que sale.").arg(Msg.euros(backend.resultCostEur))
                      : qsTr("Sin coste: se han generado desde lo que ya estaba procesado.")
            }
            Notice {
                Layout.fillWidth: true
                Layout.maximumWidth: 720
                Layout.topMargin: 16
                kind: "info"
                visible: backend.failedPages !== ""
                text: qsTr("No se han podido procesar las páginas %1. El resumen lo indica con una nota; si quieres, vuelve a generarlo más tarde y solo se procesará lo que falta.").arg(backend.failedPages)
            }

            RowLayout {
                Layout.topMargin: 32
                spacing: 48
                Sheet {
                    path: backend.summaryPath
                    primary: true
                    caption: qsTr("Resumen para estudiar")
                    openText: qsTr("Abrir resumen")
                }
                Sheet {
                    path: backend.outlinePath
                    caption: qsTr("Esquema de examen")
                    openText: qsTr("Abrir esquema")
                }
            }

            Row {
                Layout.topMargin: 32
                spacing: 12
                QuietButton {
                    implicitHeight: 40
                    text: qsTr("Mostrar en carpeta")
                    onClicked: backend.showInFolder(backend.summaryPath)
                }
                QuietButton {
                    implicitHeight: 40
                    text: qsTr("Procesar otro libro")
                    onClicked: backend.processAnother()
                }
            }
        }
    }
}
