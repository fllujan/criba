import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Criba
import "../Criba/Messages.js" as Msg

// Primer arranque (o Cambiar clave): qué es la clave, dónde se consigue y probarla.
Item {
    id: screen

    required property var backend
    readonly property bool checking: backend.keyStatus === "checking"
    readonly property bool failed: backend.keyStatus === "error"

    function test() {
        if (!checking)
            backend.testKey(keyField.text)
    }

    Flickable {
        anchors.fill: parent
        contentHeight: column.implicitHeight + 96
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {}

        ColumnLayout {
            id: column
            x: Theme.contentX
            y: 48
            width: Math.min(640, screen.width - Theme.contentX - 48)
            spacing: 0

            Text {
                Layout.fillWidth: true
                text: qsTr("Antes de empezar, conecta tu cuenta de Claude")
                color: Theme.ink
                font.family: Theme.sans
                font.pixelSize: Theme.title
                font.weight: Font.DemiBold
                font.letterSpacing: -0.4
                wrapMode: Text.WordWrap
                Accessible.role: Accessible.Heading
            }
            Body {
                Layout.fillWidth: true
                Layout.topMargin: 16
                secondary: true
                text: qsTr("Criba usa la IA de Claude con tu propia cuenta de Anthropic. La clave de API es como una contraseña que deja a Criba usarla en tu nombre: solo pagas lo que proceses y siempre ves el coste antes de empezar.")
            }

            SectionHead {
                Layout.fillWidth: true
                Layout.topMargin: 40
                number: "1"
                title: qsTr("Consigue tu clave")
            }
            Body {
                Layout.fillWidth: true
                Layout.topMargin: 8
                text: qsTr("Entra en la consola de Anthropic, abre «API Keys» y pulsa «Create Key». Copia la clave que empieza por sk-ant-.")
            }
            LinkButton {
                Layout.topMargin: 12
                text: qsTr("Abrir console.anthropic.com")
                onClicked: Qt.openUrlExternally("https://console.anthropic.com/settings/keys")
            }

            SectionHead {
                Layout.fillWidth: true
                Layout.topMargin: 40
                number: "2"
                title: qsTr("Pégala aquí")
            }
            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: 12
                spacing: 8
                Field {
                    id: keyField
                    Layout.fillWidth: true
                    implicitHeight: 40
                    echoMode: TextInput.Password
                    placeholderText: qsTr("sk-ant-…")
                    enabled: !screen.checking
                    Accessible.name: qsTr("Clave de API")
                    focus: true
                    onAccepted: screen.test()
                }
                PrimaryButton {
                    implicitHeight: 40
                    text: screen.checking ? qsTr("Comprobando…") : qsTr("Probar conexión")
                    enabled: keyField.text.trim().length > 0 && !screen.checking
                    onClicked: screen.test()
                }
            }

            // Resultado de la prueba
            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: 12
                spacing: 8
                visible: screen.checking || screen.failed
                BusyIndicator {
                    visible: screen.checking
                    running: visible
                    implicitWidth: 20
                    implicitHeight: 20
                }
                Body {
                    Layout.fillWidth: true
                    text: screen.checking ? qsTr("Comprobando la clave con Anthropic. No cuesta nada.")
                                          : Msg.error(backend.keyError)
                    color: screen.failed ? Theme.danger : Theme.muted
                    Accessible.role: screen.failed ? Accessible.AlertMessage : Accessible.StaticText
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.topMargin: 40
                height: 1
                color: Theme.hair
            }
            Body {
                Layout.fillWidth: true
                Layout.topMargin: 16
                secondary: true
                font.pixelSize: Theme.caption
                text: qsTr("La clave se guarda en el llavero de tu ordenador, nunca en un archivo. Tu libro solo sale de tu ordenador hacia Anthropic para procesarlo. Criba no recoge estadísticas de uso.")
            }
            QuietButton {
                Layout.topMargin: 24
                visible: backend.hasKey
                text: qsTr("Cancelar y seguir con la clave actual")
                onClicked: backend.cancelKeyChange()
            }
        }
    }
}
