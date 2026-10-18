import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Dialogs
import QtQuick.Layouts
import Criba
import "Criba/Messages.js" as Msg
import "screens"

ApplicationWindow {
    id: window

    required property var backend
    property string themeOverride: ""
    property string overlay: ""      // "", "settings", "history"

    title: "Criba"
    width: 1200
    height: 780
    minimumWidth: 900
    minimumHeight: 640
    visible: true
    color: Theme.paper
    font.family: Theme.sans
    font.pixelSize: Theme.body

    readonly property string screen: backend.screen
    readonly property int step: screen === "home" ? 1 : screen === "processing" ? 2 : screen === "done" ? 3 : 0

    Component.onCompleted: Theme.forced = themeOverride

    function chooseFile() { fileDialog.open() }
    function chooseFolder(retry) { folderDialog.retryRun = retry; folderDialog.open() }
    function folderChosen(url) {
        backend.setOutputDir(url)
        const writeError = backend.error === "" || backend.error === "DISK_FULL" || backend.error === "CANNOT_WRITE"
        if (folderDialog.retryRun && window.screen === "processing" && writeError)
            backend.start()
        folderDialog.retryRun = false
    }
    function openOverlay(name) { overlay = overlay === name ? "" : name; if (name === "history") backend.refreshHistory() }

    Connections {
        target: backend
        function onScreenChanged() {
            if (backend.screen !== "home" || window.overlay === "history") window.overlay = ""
        }
    }

    // --- Tapa -----------------------------------------------------------------------
    CoverBar {
        id: cover
        objectName: "cover"
        z: 2
        width: parent.width
        step: window.overlay === "" ? window.step : 0
        showNav: window.overlay === "" && window.screen !== "setup" && !backend.running
        showBack: window.overlay !== ""
        labelEditable: window.overlay === "" && window.screen === "home" && backend.hasBook
        labelTitle: window.overlay === "" && (labelEditable || window.screen === "processing" || window.screen === "done")
                    ? qsTr("Asignatura") : ""
        labelText: window.overlay === "settings" ? qsTr("Ajustes")
                 : window.overlay === "history" ? qsTr("Historial")
                 : window.screen === "setup" ? "Criba"
                 : backend.hasBook || window.screen !== "home" ? backend.subject
                 : qsTr("Elige un libro para empezar")
        labelPlaceholder: qsTr("Escribe el nombre de la asignatura")
        onLabelEdited: (t) => backend.subject = t
        onHistoryRequested: window.openOverlay("history")
        onSettingsRequested: window.openOverlay("settings")
        onBackRequested: window.overlay = ""
    }

    // --- Hoja con las pantallas -----------------------------------------------------
    Item {
        id: sheet
        anchors.top: cover.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom

        Paper { anchors.fill: parent }

        component ScreenSlot: Item {
            property bool active: false
            anchors.fill: parent
            visible: opacity > 0
            opacity: active ? 1 : 0
            enabled: active
            Behavior on opacity { NumberAnimation { duration: Theme.base; easing.type: Theme.easing } }
        }

        ScreenSlot {
            active: window.screen === "setup" && window.overlay === ""
            SetupScreen { anchors.fill: parent; backend: window.backend }
        }
        ScreenSlot {
            active: window.screen === "home" && window.overlay === ""
            HomeScreen {
                id: home
                anchors.fill: parent
                backend: window.backend
                dropHover: dropArea.containsDrag
                onChooseFile: window.chooseFile()
                onGenerate: confirmStart.open()
            }
        }
        ScreenSlot {
            active: window.screen === "processing" && window.overlay === ""
            ProcessingScreen {
                anchors.fill: parent
                backend: window.backend
                onCancelRequested: confirmCancel.open()
                onChooseFolder: window.chooseFolder(true)
            }
        }
        ScreenSlot {
            active: window.screen === "done" && window.overlay === ""
            id: doneSlot
            DoneScreen { objectName: "doneScreen"; anchors.fill: parent; backend: window.backend; active: doneSlot.active }
        }

        // Ajustes e Historial: una hoja nueva que entra desde la derecha.
        Item {
            id: overlayLayer
            readonly property bool shown: window.overlay !== ""
            width: parent.width
            height: parent.height
            visible: shown || slide.running
            onShownChanged: {
                slide.from = shown ? width : 0
                slide.to = shown ? 0 : width
                slide.restart()
            }
            NumberAnimation {
                id: slide
                target: overlayLayer
                property: "x"
                duration: Theme.base
                easing.type: Theme.easing
            }

            Paper { anchors.fill: parent }
            SettingsPage {
                anchors.fill: parent
                visible: window.overlay === "settings"
                backend: window.backend
                onChooseFolder: window.chooseFolder(false)
                onClearCacheRequested: confirmClear.open()
            }
            HistoryPage {
                anchors.fill: parent
                visible: window.overlay === "history"
                backend: window.backend
            }
        }

        // Arrastrar y soltar el PDF en cualquier parte de la hoja (RF-01).
        DropArea {
            id: dropArea
            anchors.fill: parent
            enabled: window.screen === "home" && window.overlay === "" && !backend.loading
            onEntered: (drag) => {
                const ok = drag.hasUrls && drag.urls.length > 0 && String(drag.urls[0]).toLowerCase().endsWith(".pdf")
                drag.accepted = ok
            }
            onDropped: (drop) => {
                if (drop.hasUrls && drop.urls.length > 0) {
                    backend.closeBook()
                    backend.openBook(String(drop.urls[0]))
                    drop.acceptProposedAction()
                }
            }
        }
    }

    // --- Diálogos -------------------------------------------------------------------
    FileDialog {
        id: fileDialog
        title: qsTr("Elige tu libro en PDF")
        nameFilters: [qsTr("Libros en PDF (*.pdf)")]
        onAccepted: { backend.closeBook(); backend.openBook(String(selectedFile)) }
    }
    FolderDialog {
        id: folderDialog
        objectName: "folderDialog"
        property bool retryRun: false
        title: qsTr("Elige dónde guardar los PDF")
        onAccepted: window.folderChosen(String(selectedFolder))
        onRejected: retryRun = false
    }

    ConfirmPopup {
        id: confirmStart
        objectName: "confirmStart"
        title: qsTr("¿Empezamos?")
        message: backend.estimateEur > 0
                 ? qsTr("Vas a procesar %1 páginas de «%2». Coste estimado: %3 (%4), que se cobra en tu cuenta de Anthropic. Tardará %5.")
                     .arg(Msg.integer(backend.selectedPages)).arg(backend.subject)
                     .arg(Msg.euros(backend.estimateEur)).arg(Msg.dollars(backend.estimateUsd))
                     .arg(Msg.duration(backend.estimateSeconds))
                 : qsTr("Ya está todo procesado: generar los PDF de «%1» no cuesta nada.").arg(backend.subject)
        confirmText: backend.estimateEur > 0 ? qsTr("Confirmar y empezar") : qsTr("Generar")
        onConfirmed: backend.start()
    }
    ConfirmPopup {
        id: confirmCancel
        objectName: "confirmCancel"
        title: qsTr("¿Cancelar el procesado?")
        message: qsTr("Lo ya procesado queda guardado y no se vuelve a pagar. Podrás continuar más tarde.")
        cancelText: qsTr("Seguir procesando")
        confirmText: qsTr("Cancelar")
        onConfirmed: backend.cancel()
    }
    ConfirmPopup {
        id: confirmClear
        objectName: "confirmClear"
        title: qsTr("¿Borrar lo guardado?")
        message: qsTr("Si vuelves a procesar un libro, se pagará de nuevo. Los PDF que ya tienes no se borran.")
        confirmText: qsTr("Borrar")
        onConfirmed: backend.clearCache()
    }

    // --- Teclado ----------------------------------------------------------------------
    Shortcut {
        sequences: [StandardKey.Open]
        enabled: window.screen === "home" && window.overlay === "" && !backend.loading
        onActivated: window.chooseFile()
    }
    Shortcut {
        sequences: ["Ctrl+,"]  // ⌘, en Mac
        enabled: window.screen !== "setup" && !backend.running
        onActivated: window.openOverlay("settings")
    }
    Shortcut {
        sequences: [StandardKey.Cancel]
        enabled: window.overlay !== ""
        onActivated: window.overlay = ""
    }
}
