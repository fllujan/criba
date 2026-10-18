import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Criba
import "../Criba/Messages.js" as Msg

// Procesando: etapa, capítulo, tiempo restante y coste; los capítulos se marcan en el margen.
Item {
    id: screen

    required property var backend
    signal cancelRequested()
    signal chooseFolder()

    readonly property int sideWidth: Math.max(300, Math.min(400, width * 0.3))
    readonly property int sideX: width - sideWidth - 32
    readonly property bool failed: backend.error !== "" && backend.errorWhere === "run"

    function markFor(i) {
        if (failed)
            return "off"
        switch (backend.stage) {
        case "analizando":
            if (backend.chapterIndex <= 0) return i === 0 ? "busy" : "off"
            return i < backend.chapterIndex - 1 ? "on" : i === backend.chapterIndex - 1 ? "busy" : "off"
        case "sintetizando":
            return i < backend.stepDone ? "on" : i === backend.stepDone ? "busy" : "off"
        case "generando":
        case "listo":
            return "on"
        default:
            return "off"
        }
    }

    function act(name) {
        switch (name) {
        case "reintentar": backend.start(); break
        case "cambiar_clave": backend.changeKey(); break
        case "abrir_consola": backend.openConsole(); break
        case "elegir_otra_carpeta": screen.chooseFolder(); break
        case "cancelar": screen.cancelRequested(); break
        default: backend.dismissError()
        }
    }

    // Principal: qué está pasando y los capítulos
    ColumnLayout {
        x: 0
        y: 24
        width: screen.sideX - 48
        height: parent.height - 24
        spacing: 0

        Text {
            Layout.fillWidth: true
            Layout.leftMargin: Theme.contentX
            text: screen.failed ? qsTr("Se ha detenido el procesado") : Msg.stage(backend.stage, backend.chapterIndex, backend.chapterTotal)
            color: Theme.ink
            font.family: Theme.sans
            font.pixelSize: Theme.title
            font.weight: Font.DemiBold
            font.letterSpacing: -0.4
            elide: Text.ElideRight
            Accessible.role: Accessible.Heading
        }
        Text {
            Layout.fillWidth: true
            Layout.leftMargin: Theme.contentX
            Layout.topMargin: 4
            visible: !screen.failed && backend.chapterTitle !== ""
            text: backend.chapterTitle
            color: Theme.muted
            font.family: Theme.serif
            font.italic: true
            font.pixelSize: Theme.bodyLarge
            elide: Text.ElideRight
        }
        InkBar {
            Layout.fillWidth: true
            Layout.leftMargin: Theme.contentX
            Layout.topMargin: 20
            value: backend.fraction
            opacity: screen.failed ? 0.4 : 1
        }

        Notice {
            Layout.fillWidth: true
            Layout.leftMargin: Theme.contentX
            Layout.topMargin: 24
            visible: screen.failed
            text: Msg.error(backend.error)
            actions: [
                Repeater {
                    model: backend.errorActions
                    delegate: QuietButton {
                        required property string modelData
                        text: Msg.action(modelData)
                        onClicked: screen.act(modelData)
                    }
                },
                QuietButton {
                    text: qsTr("Volver al inicio")
                    onClicked: backend.backToHome()
                }
            ]
        }
        Notice {
            Layout.fillWidth: true
            Layout.leftMargin: Theme.contentX
            Layout.topMargin: 24
            kind: "info"
            visible: !screen.failed && backend.notice === "rate_limited"
            text: Msg.error("RATE_LIMITED")
        }

        SectionHead {
            Layout.fillWidth: true
            Layout.leftMargin: Theme.contentX
            Layout.topMargin: 32
            title: qsTr("Capítulos")
            detail: qsTr("%1 páginas").arg(Msg.integer(backend.selectedPages))
        }
        ListView {
            id: list
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.topMargin: 12
            clip: true
            interactive: contentHeight > height
            boundsBehavior: Flickable.StopAtBounds
            model: backend.selectedChapters
            ScrollBar.vertical: ScrollBar {}
            Accessible.role: Accessible.List
            Accessible.name: qsTr("Capítulos en proceso")
            delegate: ChapterRow {
                required property var modelData
                width: list.width
                title: modelData.title
                firstPage: modelData.firstPage
                lastPage: modelData.lastPage
                included: true
                interactive: false
                markMode: screen.markFor(index)
            }
        }
    }

    // Lateral: tiempo, coste y Cancelar
    Rectangle {
        x: screen.sideX - 16
        width: screen.sideWidth + 32
        height: parent.height
        color: Theme.paper
    }
    ColumnLayout {
        x: screen.sideX
        y: 24
        width: screen.sideWidth
        spacing: 0

        Text {
            text: qsTr("Tiempo restante")
            color: Theme.muted
            font.family: Theme.sans
            font.pixelSize: Theme.caption
            font.weight: Font.DemiBold
        }
        Text {
            Layout.topMargin: 4
            text: screen.failed ? "—" : Msg.duration(backend.etaSeconds)
            color: Theme.ink
            font.family: Theme.sans
            font.pixelSize: Theme.heading
            font.weight: Font.DemiBold
        }
        Text {
            Layout.topMargin: 24
            text: qsTr("Gastado hasta ahora")
            color: Theme.muted
            font.family: Theme.sans
            font.pixelSize: Theme.caption
            font.weight: Font.DemiBold
        }
        Text {
            Layout.topMargin: 4
            text: Msg.euros(backend.costEur)
            color: Theme.ink
            font.family: Theme.sans
            font.pixelSize: Theme.figure
            font.weight: Font.DemiBold
            font.letterSpacing: -0.6
            font.features: { "tnum": 1 }
        }
        Body {
            Layout.fillWidth: true
            visible: backend.estimateEur > 0
            secondary: true
            font.pixelSize: Theme.caption
            text: qsTr("de unos %1 estimados").arg(Msg.euros(backend.estimateEur))
        }
        Body {
            Layout.fillWidth: true
            Layout.topMargin: 24
            secondary: true
            font.pixelSize: Theme.caption
            text: qsTr("Puedes seguir usando el ordenador. Si cancelas o cierras Criba, lo procesado queda guardado y no se vuelve a pagar.")
        }
        QuietButton {
            Layout.topMargin: 24
            implicitHeight: 40
            visible: !screen.failed
            enabled: !backend.cancelling
            text: backend.cancelling ? qsTr("Cancelando…") : qsTr("Cancelar")
            onClicked: screen.cancelRequested()
        }
    }
}
