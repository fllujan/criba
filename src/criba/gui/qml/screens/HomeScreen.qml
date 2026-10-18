import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import Criba
import "../Criba/Messages.js" as Msg

// Inicio: arrastrar el libro; luego capítulos, opciones y coste antes de Generar.
Item {
    id: screen

    required property var backend
    property bool dropHover: false
    signal chooseFile()
    signal generate()

    readonly property int sideWidth: Math.max(300, Math.min(400, width * 0.3))
    readonly property int sideX: width - sideWidth - 32
    readonly property int mainWidth: sideX - Theme.contentX - 48
    readonly property bool bookError: backend.error !== "" && backend.errorWhere === "book"

    // --- Sin libro: zona de arrastre ------------------------------------------------
    Item {
        id: empty
        anchors.fill: parent
        visible: !backend.hasBook
        opacity: visible ? 1 : 0

        ColumnLayout {
            x: Theme.contentX
            y: 48
            width: Math.min(760, parent.width - Theme.contentX - 48)
            spacing: 0

            Rectangle {
                id: drop
                Layout.fillWidth: true
                Layout.preferredHeight: Math.max(240, Math.min(360, screen.height - 280))
                radius: 12
                color: screen.dropHover ? Theme.selection : Qt.rgba(Theme.paper.r, Theme.paper.g, Theme.paper.b, 0.88)
                border.width: screen.dropHover ? 2 : 1
                border.color: screen.dropHover ? Theme.accent : Theme.fieldBorder
                Behavior on color { ColorAnimation { duration: Theme.fast } }

                // Borde discontinuo a mano: se dibuja encima del borde fino.
                Canvas {
                    anchors.fill: parent
                    visible: !screen.dropHover
                    onPaint: {
                        const ctx = getContext("2d")
                        ctx.reset()
                        ctx.strokeStyle = Theme.fieldBorder
                        ctx.lineWidth = 1.5
                        ctx.setLineDash([6, 5])
                        ctx.beginPath()
                        ctx.roundedRect(1, 1, width - 2, height - 2, 12, 12)
                        ctx.stroke()
                    }
                    onWidthChanged: requestPaint()
                    onHeightChanged: requestPaint()
                }

                ColumnLayout {
                    anchors.centerIn: parent
                    width: Math.min(parent.width - 64, 440)
                    spacing: 12
                    visible: !backend.loading

                    Text {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        text: screen.dropHover ? qsTr("Suelta el libro aquí") : qsTr("Arrastra aquí tu libro en PDF")
                        color: Theme.ink
                        font.family: Theme.sans
                        font.pixelSize: Theme.title
                        font.weight: Font.DemiBold
                        font.letterSpacing: -0.4
                        wrapMode: Text.WordWrap
                    }
                    Body {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        secondary: true
                        text: qsTr("Leerlo y calcular el coste es gratis y no sale de tu ordenador.")
                    }
                    QuietButton {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.topMargin: 8
                        implicitHeight: 40
                        text: qsTr("Elegir archivo…")
                        onClicked: screen.chooseFile()
                    }
                }

                // Leyendo el libro (local)
                ColumnLayout {
                    anchors.centerIn: parent
                    width: Math.min(parent.width - 64, 400)
                    spacing: 12
                    visible: backend.loading
                    Text {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        text: qsTr("Leyendo el libro…")
                        color: Theme.ink
                        font.family: Theme.sans
                        font.pixelSize: Theme.heading
                        font.weight: Font.DemiBold
                    }
                    InkBar {
                        Layout.fillWidth: true
                        value: backend.loadFraction
                    }
                    Body {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        secondary: true
                        text: qsTr("Página a página, sin conexión. En un libro largo tarda unos segundos.")
                    }
                }
            }

            Notice {
                Layout.fillWidth: true
                Layout.topMargin: 24
                visible: screen.bookError
                text: Msg.error(backend.error)
                actions: [
                    QuietButton {
                        text: Msg.action("elegir_otro_archivo")
                        onClicked: { backend.dismissError(); screen.chooseFile() }
                    }
                ]
            }

            // Continuar donde lo dejaste (RNF-06)
            Notice {
                Layout.fillWidth: true
                Layout.topMargin: 24
                kind: "info"
                visible: backend.resumeTitle !== "" && !backend.loading
                text: qsTr("Tienes a medias «%1». Lo ya procesado está guardado: si sigues, no se vuelve a pagar.").arg(backend.resumeTitle)
                actions: [
                    QuietButton {
                        text: qsTr("Continuar donde lo dejaste")
                        onClicked: backend.resume()
                    }
                ]
            }
        }
    }

    // --- Con libro: capítulos, opciones y coste ---------------------------------
    Item {
        id: loaded
        anchors.fill: parent
        visible: backend.hasBook

        // Columna principal
        ColumnLayout {
            id: mainCol
            x: 0
            y: 24
            width: Theme.contentX + screen.mainWidth
            height: parent.height - 24
            spacing: 0

            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: Theme.contentX
                Layout.preferredHeight: Theme.row
                spacing: 12
                Text {
                    text: backend.fileName
                    color: Theme.ink
                    font.family: Theme.sans
                    font.pixelSize: Theme.body
                    font.weight: Font.DemiBold
                    elide: Text.ElideMiddle
                    Layout.maximumWidth: screen.mainWidth * 0.5
                }
                Text {
                    Layout.fillWidth: true
                    text: backend.scannedPages > 0
                          ? qsTr("%1 páginas · %2 escaneadas (se leerán con la IA)").arg(Msg.integer(backend.pageCount)).arg(backend.scannedPages)
                          : qsTr("%1 páginas").arg(Msg.integer(backend.pageCount))
                    color: Theme.muted
                    font.family: Theme.sans
                    font.pixelSize: Theme.body
                    elide: Text.ElideRight
                }
                QuietButton {
                    text: qsTr("Cambiar libro")
                    onClicked: { backend.closeBook(); screen.chooseFile() }
                }
            }

            SectionHead {
                Layout.fillWidth: true
                Layout.leftMargin: Theme.contentX
                Layout.topMargin: 24
                number: "1"
                title: qsTr("Capítulos")
                detail: qsTr("%1 de %2 incluidos · %3 páginas").arg(backend.checkedCount).arg(backend.chapterCount).arg(Msg.integer(backend.selectedPages))
            }
            Body {
                Layout.fillWidth: true
                Layout.leftMargin: Theme.contentX
                Layout.topMargin: 4
                secondary: true
                font.pixelSize: Theme.caption
                visible: backend.chapterSource === "bloques"
                text: qsTr("Este PDF no tiene índice ni títulos claros, así que lo hemos dividido en bloques de páginas.")
            }

            ListView {
                id: chapterList
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.topMargin: 12
                clip: true
                model: backend.chapterModel
                boundsBehavior: Flickable.StopAtBounds
                keyNavigationEnabled: true
                activeFocusOnTab: true
                ScrollBar.vertical: ScrollBar {}
                Accessible.role: Accessible.List
                Accessible.name: qsTr("Capítulos detectados")

                delegate: ChapterRow {
                    width: chapterList.width
                    highlighted: chapterList.activeFocus && ListView.isCurrentItem
                    onIncludeToggled: (included) => backend.setChapterChecked(index, included)
                }
                Keys.onSpacePressed: {
                    const item = chapterList.currentItem
                    if (item) backend.setChapterChecked(chapterList.currentIndex, !item.included)
                }
                Rectangle {
                    width: parent.width - Theme.contentX
                    x: Theme.contentX
                    height: 1
                    color: Theme.hair
                }
            }

            // Rango de páginas opcional (RF-05)
            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: Theme.contentX
                Layout.preferredHeight: 48
                spacing: 16
                LinkButton {
                    text: backend.chapterCount > 0 && backend.checkedCount === backend.chapterCount ? qsTr("Quitar todos") : qsTr("Marcar todos")
                    onClicked: backend.setAllChapters(backend.checkedCount !== backend.chapterCount)
                }
                LinkButton {
                    visible: !rangeRow.visible
                    text: qsTr("Elegir un rango de páginas")
                    onClicked: { rangeRow.visible = true; fromField.forceActiveFocus() }
                }
                RowLayout {
                    id: rangeRow
                    visible: backend.pageFrom > 0
                    spacing: 8
                    Body { text: qsTr("De la página") }
                    Field {
                        id: fromField
                        implicitWidth: 72
                        implicitHeight: 32
                        text: backend.pageFrom > 0 ? backend.pageFrom : ""
                        validator: IntValidator { bottom: 1; top: backend.pageCount }
                        inputMethodHints: Qt.ImhDigitsOnly
                        Accessible.name: qsTr("Primera página")
                        onEditingFinished: screen.applyRange()
                    }
                    Body { text: qsTr("a la") }
                    Field {
                        id: toField
                        implicitWidth: 72
                        implicitHeight: 32
                        text: backend.pageTo > 0 ? backend.pageTo : ""
                        validator: IntValidator { bottom: 1; top: backend.pageCount }
                        inputMethodHints: Qt.ImhDigitsOnly
                        Accessible.name: qsTr("Última página")
                        onEditingFinished: screen.applyRange()
                    }
                    LinkButton {
                        text: qsTr("Quitar el rango")
                        onClicked: { fromField.text = ""; toField.text = ""; backend.setPageRange(0, 0); rangeRow.visible = false }
                    }
                }
                Item { Layout.fillWidth: true }
            }
        }

        // Columna derecha: opciones, coste y Generar
        Rectangle {
            x: screen.sideX - 16
            width: screen.sideWidth + 32
            height: parent.height
            color: Theme.paper
        }
        Flickable {
            // Empieza 48 px antes para que los números rodeados del margen no se recorten.
            x: screen.sideX - 48
            width: screen.sideWidth + 48
            height: parent.height
            contentHeight: side.implicitHeight + 48
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            ColumnLayout {
                id: side
                x: 48
                width: screen.sideWidth
                y: 24
                spacing: 0

                SectionHead {
                    Layout.fillWidth: true
                    number: "2"
                    title: qsTr("Opciones")
                    ringOffset: -44
                }
                Text {
                    Layout.topMargin: 16
                    text: qsTr("Nivel de detalle")
                    color: Theme.ink
                    font.family: Theme.sans
                    font.pixelSize: Theme.caption
                    font.weight: Font.DemiBold
                }
                Segmented {
                    Layout.fillWidth: true
                    Layout.topMargin: 8
                    accessibleName: qsTr("Nivel de detalle")
                    value: backend.level
                    options: [
                        { value: "esencial", label: qsTr("Esencial"), hint: qsTr("≈10 % del libro") },
                        { value: "normal", label: qsTr("Normal"), hint: qsTr("≈15 %") },
                        { value: "completo", label: qsTr("Completo"), hint: qsTr("≈20 %") }
                    ]
                    onActivated: (v) => backend.level = v
                }
                Text {
                    Layout.topMargin: 24
                    text: qsTr("Tipo de examen")
                    color: Theme.ink
                    font.family: Theme.sans
                    font.pixelSize: Theme.caption
                    font.weight: Font.DemiBold
                }
                Segmented {
                    Layout.fillWidth: true
                    Layout.topMargin: 8
                    accessibleName: qsTr("Tipo de examen")
                    value: backend.examType
                    options: [
                        { value: "test", label: qsTr("Test") },
                        { value: "desarrollo", label: qsTr("Desarrollo") },
                        { value: "mixto", label: qsTr("Mixto") }
                    ]
                    onActivated: (v) => backend.examType = v
                }
                Body {
                    Layout.fillWidth: true
                    Layout.topMargin: 8
                    secondary: true
                    font.pixelSize: Theme.caption
                    text: backend.examType === "test" ? qsTr("Las preguntas probables serán de opción múltiple, con soluciones.")
                        : backend.examType === "desarrollo" ? qsTr("Las preguntas probables serán para desarrollar, con guion de respuesta.")
                        : qsTr("Mezcla de preguntas tipo test y de desarrollo.")
                }

                SectionHead {
                    Layout.fillWidth: true
                    Layout.topMargin: 40
                    number: "3"
                    title: qsTr("Coste estimado")
                    ringOffset: -44
                }
                RowLayout {
                    Layout.topMargin: 12
                    spacing: 12
                    opacity: backend.estimating ? 0.45 : 1
                    Behavior on opacity { NumberAnimation { duration: Theme.fast } }
                    Text {
                        text: backend.estimateCalls > 0 && backend.estimateEur === 0 ? qsTr("Gratis") : "≈ " + Msg.euros(backend.estimateEur)
                        color: Theme.ink
                        font.family: Theme.sans
                        font.pixelSize: Theme.figure
                        font.weight: Font.DemiBold
                        font.letterSpacing: -0.6
                        font.features: { "tnum": 1 }
                        Accessible.name: qsTr("Coste estimado: %1").arg(text)
                    }
                    Text {
                        visible: backend.estimateEur > 0
                        text: Msg.dollars(backend.estimateUsd)
                        color: Theme.muted
                        font.family: Theme.sans
                        font.pixelSize: Theme.bodyLarge
                        font.features: { "tnum": 1 }
                    }
                }
                Body {
                    Layout.fillWidth: true
                    text: backend.estimateCalls === 0
                          ? qsTr("Marca al menos un capítulo con texto.")
                          : qsTr("%1 páginas · unas %2 llamadas a la IA · %3").arg(Msg.integer(backend.selectedPages)).arg(backend.estimateCalls - backend.estimateCachedCalls).arg(Msg.duration(backend.estimateSeconds))
                    font.pixelSize: Theme.caption
                }
                Body {
                    Layout.fillWidth: true
                    Layout.topMargin: 12
                    secondary: true
                    font.pixelSize: Theme.caption
                    text: backend.estimateCachedCalls > 0 && backend.estimateEur === 0
                          ? qsTr("Ya lo procesaste con estas opciones: generar los PDF no cuesta nada.")
                          : backend.estimateCachedCalls > 0
                            ? qsTr("Parte ya está procesada y no se vuelve a pagar. Si cancelas, lo hecho se guarda.")
                            : qsTr("Solo pagas lo que proceses. Si cancelas, lo hecho se guarda.")
                }
                Notice {
                    Layout.fillWidth: true
                    Layout.topMargin: 16
                    kind: "info"
                    visible: backend.notice === "cancelled"
                    text: qsTr("Has cancelado. Lo procesado está guardado: el coste de arriba es solo lo que falta.")
                }
                PrimaryButton {
                    objectName: "generateButton"
                    Layout.fillWidth: true
                    Layout.topMargin: 32
                    text: qsTr("Generar resumen y esquema")
                    enabled: backend.estimateCalls > 0 && !backend.estimating && backend.subject.trim() !== ""
                    onClicked: screen.generate()
                }
            }
        }
    }

    function applyRange() {
        const a = parseInt(fromField.text), b = parseInt(toField.text)
        if (a > 0 && b > 0)
            backend.setPageRange(a, b)
    }
}
