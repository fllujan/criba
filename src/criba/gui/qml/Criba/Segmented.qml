import QtQuick
import QtQuick.Controls.Basic

// Control segmentado (una opción entre pocas). Flechas del teclado para moverse.
FocusScope {
    id: seg

    // [{ value, label, hint }]
    property var options: []
    property string value: ""
    property string accessibleName: ""
    signal activated(string value)

    implicitHeight: frame.implicitHeight
    implicitWidth: 320
    activeFocusOnTab: true
    Accessible.role: Accessible.RadioButton
    Accessible.name: accessibleName

    function move(step) {
        const i = options.findIndex(o => o.value === value)
        const next = options[Math.max(0, Math.min(options.length - 1, i + step))]
        if (next && next.value !== value)
            activated(next.value)
    }
    Keys.onLeftPressed: move(-1)
    Keys.onRightPressed: move(1)

    Rectangle {
        id: frame
        anchors.fill: parent
        implicitHeight: (seg.options.some(o => o.hint) ? 44 : 32) + 6
        radius: 8
        color: Theme.field
        border.width: 1
        border.color: Theme.fieldBorder
        FocusRing { shown: seg.activeFocus }

        Row {
            anchors.fill: parent
            anchors.margins: 3
            spacing: 3
            Repeater {
                model: seg.options
                delegate: AbstractButton {
                    id: opt
                    required property var modelData
                    readonly property bool current: modelData.value === seg.value
                    width: (frame.width - 6 - 3 * (seg.options.length - 1)) / seg.options.length
                    height: parent.height
                    hoverEnabled: true
                    focusPolicy: Qt.NoFocus
                    Accessible.role: Accessible.RadioButton
                    Accessible.name: modelData.label
                    Accessible.checked: current
                    onClicked: { seg.forceActiveFocus(); seg.activated(modelData.value) }

                    background: Rectangle {
                        radius: 5
                        color: opt.current ? Theme.selection : opt.hovered ? Qt.rgba(Theme.selection.r, Theme.selection.g, Theme.selection.b, 0.6) : "transparent"
                        border.width: opt.current ? 2 : 0
                        border.color: Theme.accent
                        Behavior on color { ColorAnimation { duration: Theme.fast } }
                    }
                    contentItem: Column {
                        spacing: 0
                        Item { width: 1; height: (opt.height - implicitHeightOf()) / 2
                            function implicitHeightOf() { return lbl.implicitHeight + (hint.visible ? hint.implicitHeight : 0) } }
                        Text {
                            id: lbl
                            width: opt.width
                            horizontalAlignment: Text.AlignHCenter
                            text: opt.modelData.label
                            color: opt.current ? Theme.accentInk : Theme.ink
                            font.family: Theme.sans
                            font.pixelSize: Theme.body
                            font.weight: opt.current ? Font.Bold : Font.Medium
                            elide: Text.ElideRight
                        }
                        Text {
                            id: hint
                            visible: !!opt.modelData.hint
                            width: opt.width
                            horizontalAlignment: Text.AlignHCenter
                            text: opt.modelData.hint || ""
                            color: opt.current ? Theme.accentInk : Theme.muted
                            font.family: Theme.sans
                            font.pixelSize: Theme.small
                        }
                    }
                }
            }
        }
    }
}
