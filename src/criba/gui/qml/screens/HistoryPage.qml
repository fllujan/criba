import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Criba
import "../Criba/Messages.js" as Msg

// Historial (RF-18): libros procesados; abrirlos o regenerarlos gratis.
Item {
    id: page

    required property var backend
    readonly property int count: backend ? backend.historyCount : 0
    signal opened()

    ColumnLayout {
        x: 0
        y: 32
        width: Math.min(Theme.contentX + 860, page.width - 48)
        height: page.height - 32
        spacing: 0

        SectionHead {
            Layout.fillWidth: true
            Layout.leftMargin: Theme.contentX
            title: qsTr("Libros procesados")
            detail: page.count > 0 ? Msg.books(page.count) : ""
        }
        Body {
            Layout.fillWidth: true
            Layout.leftMargin: Theme.contentX
            Layout.topMargin: 16
            visible: page.count === 0
            secondary: true
            text: qsTr("Aún no has procesado ningún libro. Cuando lo hagas, aparecerá aquí para abrirlo o volver a generarlo sin coste.")
        }
        Notice {
            Layout.fillWidth: true
            Layout.leftMargin: Theme.contentX
            Layout.topMargin: 16
            visible: backend.error !== "" && backend.errorWhere === "history"
            text: qsTr("No se encuentran los datos de ese libro. Vuelve a procesarlo desde Inicio; lo que ya estaba procesado no se paga.")
            actions: [ QuietButton { text: qsTr("Entendido"); onClicked: backend.dismissError() } ]
        }

        ListView {
            id: list
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.topMargin: 16
            clip: true
            model: backend.historyModel
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar {}
            Accessible.role: Accessible.List
            Accessible.name: qsTr("Libros procesados")

            delegate: Item {
                id: entry
                required property int jobId
                required property string title
                required property string date
                required property real costUsd
                required property string summary
                required property string outline
                required property string dataFile
                required property bool available
                width: list.width
                height: 64

                Mark {
                    x: 82
                    anchors.verticalCenter: parent.verticalCenter
                    mode: entry.available ? "on" : "off"
                }
                Text {
                    x: 0
                    width: 72
                    anchors.verticalCenter: parent.verticalCenter
                    horizontalAlignment: Text.AlignRight
                    text: Msg.date(entry.date)
                    color: Theme.pen
                    font.family: Theme.serif
                    font.italic: true
                    font.pixelSize: Theme.small
                    wrapMode: Text.WordWrap
                    maximumLineCount: 2
                }
                Rectangle {
                    x: Theme.contentX
                    width: parent.width - Theme.contentX
                    height: parent.height
                    color: Theme.paper
                    Rectangle { width: parent.width; height: 1; color: Theme.hair }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 4
                        spacing: 8
                        Column {
                            Layout.fillWidth: true
                            spacing: 2
                            Text {
                                width: parent.width
                                text: entry.title
                                color: Theme.ink
                                font.family: Theme.serif
                                font.pixelSize: Theme.bodyLarge
                                elide: Text.ElideRight
                            }
                            Text {
                                width: parent.width
                                text: entry.available ? qsTr("Los dos PDF están en su carpeta.")
                                                      : qsTr("Falta algún PDF: puedes regenerarlo gratis.")
                                color: Theme.muted
                                font.family: Theme.sans
                                font.pixelSize: Theme.caption
                                elide: Text.ElideRight
                            }
                        }
                        QuietButton {
                            visible: entry.available
                            text: qsTr("Abrir resumen")
                            onClicked: backend.openFile(entry.summary)
                        }
                        QuietButton {
                            visible: entry.available
                            text: qsTr("Abrir esquema")
                            onClicked: backend.openFile(entry.outline)
                        }
                        QuietButton {
                            text: qsTr("Regenerar")
                            enabled: entry.dataFile !== ""
                            onClicked: backend.regenerate(entry.jobId)
                        }
                    }
                }
            }
        }
    }
}
