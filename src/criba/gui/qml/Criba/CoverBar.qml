import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// La tapa del cuaderno: etiqueta con la asignatura, pasos y accesos siempre visibles.
Rectangle {
    id: bar

    property int step: 0                 // 0 = sin pasos; 1 Libro, 2 Procesar, 3 Listo
    property string labelTitle: "Criba"
    property string labelText: ""
    property bool labelEditable: false
    property string labelPlaceholder: ""
    property bool showNav: true
    property bool showBack: false
    signal labelEdited(string text)
    signal historyRequested()
    signal settingsRequested()
    signal backRequested()

    implicitHeight: 80
    color: Theme.cover
    readonly property bool narrow: width < 1000

    // El campo se edita a mano; si la asignatura cambia desde fuera (otro libro), se actualiza.
    onLabelTextChanged: if (labelInput.text !== labelText) labelInput.text = labelText

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 24
        anchors.rightMargin: 24
        spacing: 24

        // Etiqueta blanca de la tapa: aquí se escribe la asignatura.
        Rectangle {
            Layout.preferredWidth: bar.narrow ? bar.width * 0.30 : Math.min(400, bar.width * 0.36)
            Layout.preferredHeight: 52
            radius: 10
            color: Theme.label

            Column {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.leftMargin: 16
                anchors.rightMargin: 16
                anchors.verticalCenter: parent.verticalCenter
                spacing: 1
                Text {
                    visible: bar.labelTitle !== ""
                    text: bar.labelTitle
                    color: Theme.accentInk
                    font.family: Theme.sans
                    font.pixelSize: Theme.small
                    font.weight: Font.Bold
                    font.letterSpacing: 0.3
                }
                TextInput {
                    id: labelInput
                    objectName: "subjectInput"
                    width: parent.width
                    visible: bar.labelEditable
                    Component.onCompleted: text = bar.labelText
                    color: activeFocus ? Theme.ink : "transparent"
                    font.family: Theme.sans
                    font.pixelSize: Theme.bodyLarge
                    font.weight: Font.Medium
                    clip: true
                    autoScroll: activeFocus  // sin foco se ve el principio del nombre
                    selectByMouse: true
                    selectionColor: Theme.accent
                    selectedTextColor: Theme.coverInk
                    maximumLength: 120
                    Accessible.role: Accessible.EditableText
                    Accessible.name: qsTr("Asignatura")
                    onTextEdited: bar.labelEdited(text)
                    Text {
                        visible: !labelInput.text
                        text: bar.labelPlaceholder
                        color: Theme.muted
                        font: labelInput.font
                    }
                    // Sin foco: el nombre entero con «…» si no cabe; al editar, el campo real.
                    Text {
                        objectName: "subjectPreview"
                        anchors.fill: parent
                        visible: !labelInput.activeFocus && labelInput.text !== ""
                        text: labelInput.text
                        color: Theme.ink
                        font: labelInput.font
                        elide: Text.ElideRight
                    }
                }
                // Raya discontinua: aquí se escribe, como en la etiqueta de la tapa.
                Row {
                    visible: bar.labelEditable
                    spacing: 3
                    Repeater {
                        model: Math.max(0, Math.ceil(labelInput.width / 6))
                        delegate: Rectangle {
                            width: 3
                            height: labelInput.activeFocus ? 2 : 1
                            color: labelInput.activeFocus ? Theme.pen : Theme.fieldBorder
                        }
                    }
                }
                Text {
                    visible: !bar.labelEditable
                    width: parent.width
                    text: bar.labelText
                    color: Theme.ink
                    font.family: Theme.sans
                    font.pixelSize: Theme.bodyLarge
                    font.weight: Font.Medium
                    elide: Text.ElideRight
                }
            }
        }

        // Pasos: 1 Libro · 2 Procesar · 3 Listo
        Row {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignCenter
            spacing: bar.narrow ? 16 : 28
            visible: bar.step > 0
            Accessible.role: Accessible.List
            Accessible.name: qsTr("Pasos")
            Repeater {
                model: [qsTr("Libro"), qsTr("Procesar"), qsTr("Listo")]
                delegate: Row {
                    id: stepItem
                    required property string modelData
                    required property int index
                    readonly property bool current: index + 1 === bar.step
                    readonly property bool past: index + 1 < bar.step
                    spacing: 8
                    Accessible.role: Accessible.ListItem
                    Accessible.name: modelData + (current ? qsTr(" (paso actual)") : "")
                    Rectangle {
                        width: 22; height: 22; radius: 11
                        anchors.verticalCenter: parent.verticalCenter
                        color: stepItem.current || stepItem.past ? Theme.coverInk : "transparent"
                        border.width: 1
                        border.color: stepItem.current || stepItem.past ? Theme.coverInk : Theme.coverMuted
                        Text {
                            anchors.centerIn: parent
                            text: stepItem.index + 1
                            color: stepItem.current || stepItem.past ? Theme.cover : Theme.coverMuted
                            font.family: Theme.sans
                            font.pixelSize: Theme.small
                            font.weight: Font.Bold
                        }
                    }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        visible: stepItem.current || !bar.narrow
                        text: stepItem.modelData
                        color: stepItem.current ? Theme.coverInk : Theme.coverMuted
                        font.family: Theme.sans
                        font.pixelSize: Theme.body
                        font.weight: stepItem.current ? Font.Bold : Font.Medium
                    }
                }
            }
        }
        Item { Layout.fillWidth: true; visible: bar.step === 0 }

        Row {
            spacing: 4
            visible: bar.showNav
            CoverButton {
                text: qsTr("Historial")
                iconSource: "../../../assets/icons/history.svg"
                onClicked: bar.historyRequested()
            }
            CoverButton {
                text: qsTr("Ajustes")
                iconSource: "../../../assets/icons/settings.svg"
                onClicked: bar.settingsRequested()
            }
        }
        CoverButton {
            visible: bar.showBack
            text: qsTr("Volver")
            onClicked: bar.backRequested()
        }
    }
}
