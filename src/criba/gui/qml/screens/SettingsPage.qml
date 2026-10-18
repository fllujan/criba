import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Criba
import "../Criba/Messages.js" as Msg

// Ajustes (RF-17): clave, modelo, carpeta, idioma, caché y privacidad.
Item {
    id: page

    required property var backend
    signal chooseFolder()
    signal clearCacheRequested()

    Flickable {
        anchors.fill: parent
        contentHeight: column.implicitHeight + 96
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {}

        ColumnLayout {
            id: column
            x: Theme.contentX
            y: 32
            width: Math.min(680, page.width - Theme.contentX - 48)
            spacing: 0

            SectionHead { Layout.fillWidth: true; number: "1"; title: qsTr("Clave de API") }
            Body {
                Layout.fillWidth: true
                Layout.topMargin: 8
                text: backend.hasKey
                      ? qsTr("Guardada en el llavero de tu ordenador%1.").arg(backend.keyHint ? qsTr(" (termina en %1)").arg(backend.keyHint.replace("…", "")) : "")
                      : qsTr("No hay ninguna clave guardada.")
            }
            Row {
                Layout.topMargin: 12
                spacing: 8
                QuietButton { text: qsTr("Cambiar clave"); onClicked: backend.changeKey() }
                QuietButton {
                    visible: backend.hasKey
                    destructive: true
                    text: qsTr("Borrar clave")
                    onClicked: backend.forgetKey()
                }
            }

            SectionHead { Layout.fillWidth: true; Layout.topMargin: 40; number: "2"; title: qsTr("Modelo de IA") }
            ButtonGroup { id: modelGroup }
            Repeater {
                model: backend.models
                delegate: RadioDelegate {
                    id: option
                    required property string modelData
                    Layout.fillWidth: true
                    Layout.topMargin: 4
                    checked: backend.model === modelData
                    ButtonGroup.group: modelGroup
                    onClicked: backend.setModel(modelData)
                    padding: 8
                    leftPadding: 36
                    Accessible.name: Msg.model(modelData) + ". " + Msg.modelHint(modelData)
                    background: Rectangle {
                        radius: 6
                        color: option.checked ? Theme.selection : option.hovered ? Qt.rgba(Theme.selection.r, Theme.selection.g, Theme.selection.b, 0.5) : "transparent"
                        FocusRing { shown: option.visualFocus }
                    }
                    indicator: Rectangle {
                        x: 10
                        anchors.verticalCenter: parent.verticalCenter
                        width: 16; height: 16; radius: 8
                        color: Theme.field
                        border.width: option.checked ? 5 : 1
                        border.color: option.checked ? Theme.accent : Theme.fieldBorder
                    }
                    contentItem: Column {
                        spacing: 2
                        Text {
                            text: Msg.model(option.modelData)
                            color: Theme.ink
                            font.family: Theme.sans
                            font.pixelSize: Theme.body
                            font.weight: Font.DemiBold
                        }
                        Text {
                            text: Msg.modelHint(option.modelData)
                            color: Theme.muted
                            font.family: Theme.sans
                            font.pixelSize: Theme.caption
                        }
                    }
                }
            }

            SectionHead { Layout.fillWidth: true; Layout.topMargin: 40; number: "3"; title: qsTr("Carpeta de los PDF") }
            Text {
                Layout.fillWidth: true
                Layout.topMargin: 8
                text: backend.outputDir
                color: Theme.ink
                font.family: Theme.sans
                font.pixelSize: Theme.body
                elide: Text.ElideMiddle
            }
            Row {
                Layout.topMargin: 12
                spacing: 8
                QuietButton { text: qsTr("Elegir carpeta…"); onClicked: page.chooseFolder() }
                QuietButton { text: qsTr("Abrir"); onClicked: backend.showInFolder(backend.outputDir) }
                QuietButton { text: qsTr("Usar Documentos/Criba"); onClicked: backend.setOutputDir("") }
            }

            SectionHead { Layout.fillWidth: true; Layout.topMargin: 40; number: "4"; title: qsTr("Idioma de los PDF") }
            ComboBox {
                id: languageBox
                Layout.topMargin: 12
                Layout.preferredWidth: 320
                implicitHeight: 36
                model: [""].concat(backend.languages)
                currentIndex: Math.max(0, model.indexOf(backend.language))
                displayText: Msg.language(currentValue)
                font.family: Theme.sans
                font.pixelSize: Theme.body
                Accessible.name: qsTr("Idioma de los PDF")
                onActivated: (i) => backend.setLanguage(model[i])
                delegate: ItemDelegate {
                    required property var modelData
                    required property int index
                    width: languageBox.width
                    text: Msg.language(modelData)
                    font: languageBox.font
                    highlighted: languageBox.highlightedIndex === index
                }
                background: Rectangle {
                    radius: 6
                    color: Theme.field
                    border.width: languageBox.visualFocus ? 2 : 1
                    border.color: languageBox.visualFocus ? Theme.pen : Theme.fieldBorder
                }
                contentItem: Text {
                    leftPadding: 12
                    text: languageBox.displayText
                    font: languageBox.font
                    color: Theme.ink
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }
            }

            SectionHead { Layout.fillWidth: true; Layout.topMargin: 40; number: "5"; title: qsTr("Lo ya procesado") }
            Body {
                Layout.fillWidth: true
                Layout.topMargin: 8
                text: backend.cacheEntries === 1 ? qsTr("Criba guarda cada parte que procesa para no cobrártela dos veces y para regenerar los PDF gratis. Ahora hay 1 parte guardada.") : qsTr("Criba guarda cada parte que procesa para no cobrártela dos veces y para regenerar los PDF gratis. Ahora hay %1 partes guardadas.").arg(Msg.integer(backend.cacheEntries))
            }
            QuietButton {
                Layout.topMargin: 12
                destructive: true
                enabled: backend.cacheEntries > 0
                text: qsTr("Borrar lo guardado…")
                onClicked: page.clearCacheRequested()
            }

            SectionHead { Layout.fillWidth: true; Layout.topMargin: 40; number: "6"; title: qsTr("Privacidad") }
            Body {
                Layout.fillWidth: true
                Layout.topMargin: 8
                text: qsTr("Tu libro solo sale de tu ordenador hacia Anthropic, la empresa de la IA, para procesarlo. Criba no tiene cuentas, ni nube, ni estadísticas de uso. La clave vive en el llavero del sistema.")
            }
            LinkButton {
                Layout.topMargin: 12
                text: qsTr("Abrir la carpeta de registros")
                onClicked: backend.openLogs()
            }
            Body {
                Layout.topMargin: 32
                secondary: true
                font.pixelSize: Theme.small
                text: qsTr("Criba %1").arg(Qt.application.version)
            }
        }
    }
}
