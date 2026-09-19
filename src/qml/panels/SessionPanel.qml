import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

Rectangle {
    id: panel

    // Folder queued for deletion, shown by the confirmation dialog.
    property string pendingDeleteFolder: ""

    // True while a session tile is being dragged; reveals the unfiled drop zone.
    property bool dragActive: false

    color: Theme.colors.surfaceBg
    border.color: Theme.colors.borderDefault
    border.width: 1

    // ------------------------------------------------------------------
    //  Reusable buttons
    // ------------------------------------------------------------------

    component PanelButton: Button {
        id: control

        property color baseColor: Theme.colors.surfaceBg
        property color labelColor: Theme.colors.textPrimary

        implicitHeight: 28
        implicitWidth: 84
        font.family: Theme.fontMono
        font.pointSize: Theme.metrics.fontSizeBase

        background: Rectangle {
            color: control.down ? Theme.colors.hoverBg : control.baseColor
            radius: Theme.metrics.buttonRadius
            border.color: Theme.colors.borderDefault
            border.width: 1
        }

        contentItem: Text {
            text: control.text
            color: control.labelColor
            font: control.font
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ----------------------------------------------------------
        //  Session sidebar
        // ----------------------------------------------------------
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            RowLayout {
                Layout.fillWidth: true
                Layout.margins: 8
                spacing: 6

                PanelButton {
                    Layout.fillWidth: true
                    text: qsTr("+ Session")
                    baseColor: Theme.colors.buttonPrimaryBg
                    labelColor: Theme.colors.buttonPrimaryFg
                    onClicked: session._handle_new_session()
                }

                PanelButton {
                    Layout.fillWidth: true
                    text: qsTr("+ Folder")
                    onClicked: session._handle_new_folder()
                }
            }

            ListView {
                id: sessionList
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                spacing: 0
                model: session.session_model

                delegate: Item {
                    width: sessionList.width
                    height: model.is_folder ? 34 : 48

                    SessionTile {
                        anchors.fill: parent
                        visible: !model.is_folder
                        sessionId: model.session_id
                        title: model.title
                        status: model.status
                        isActive: model.is_active
                        isBlinking: model.is_blinking
                        messageCount: model.message_count
                        dotColor: session.statusColor(model.status)
                        onClicked: session._handle_session_click(model.session_id)
                        onDeleteRequested: session._handle_delete_session(model.session_id)
                        onDragBegan: panel.dragActive = true
                        onDragFinished: panel.dragActive = false
                    }

                    FolderHeader {
                        anchors.fill: parent
                        visible: model.is_folder
                        folderName: model.folder
                        sessionCount: model.message_count
                        expanded: session.is_folder_expanded(model.folder)
                        onToggled: function (expanded) {
                            session._handle_folder_expansion(model.folder, expanded)
                        }
                        onDeleteRequested: {
                            panel.pendingDeleteFolder = model.folder
                            deleteFolderDialog.open()
                        }
                        onDropOnFolder: function (sessionId, folder) {
                            session._handle_drop_on_folder(sessionId, folder)
                        }
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------------
    //  Unfiled drop zone (revealed while dragging a session tile)
    // ------------------------------------------------------------------

    Rectangle {
        id: unfiledZone
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 44
        z: 50
        visible: panel.dragActive
        color: Theme.colors.surfaceBg
        border.color: unfiledDrop.containsDrag ? Theme.colors.dragFeedbackBorder
                                               : Theme.colors.borderDefault
        border.width: unfiledDrop.containsDrag ? 2 : 1
        radius: Theme.metrics.dropZoneRadius

        Text {
            anchors.centerIn: parent
            text: qsTr("Unfiled")
            color: Theme.colors.textSecondary
            font.family: Theme.fontMono
            font.pointSize: Theme.metrics.fontSizeBase
        }

        DropArea {
            id: unfiledDrop
            anchors.fill: parent
            keys: ["session"]

            onDropped: function (drop) {
                var sessionId = panel.sessionIdFromDrop(drop)
                if (sessionId !== "")
                    session._handle_drop_on_folder(sessionId, "")
                drop.acceptProposedAction()
            }
        }
    }

    // ------------------------------------------------------------------
    //  Drop helpers
    // ------------------------------------------------------------------

    function sessionIdFromDrop(drop) {
        if (drop.source && drop.source.sessionId !== undefined)
            return drop.source.sessionId
        if (drop.formats && drop.formats.indexOf("text/plain") !== -1)
            return drop.getDataAsString("text/plain")
        return ""
    }

    // ------------------------------------------------------------------
    //  New folder dialog
    // ------------------------------------------------------------------

    Dialog {
        id: newFolderDialog
        anchors.centerIn: Overlay.overlay
        modal: true
        focus: true
        width: 320
        padding: 12
        background: Rectangle {
            color: Theme.colors.surfaceBg
            border.color: Theme.colors.borderDefault
            border.width: 1
            radius: 0
        }
        contentItem: ColumnLayout {
            spacing: 8
            Text {
                text: qsTr("Folder name")
                color: Theme.colors.textPrimary
                font.family: Theme.fontMono
                font.pointSize: Theme.metrics.fontSizeBase
            }
            TextField {
                id: folderNameField
                Layout.fillWidth: true
                placeholderText: qsTr("New folder")
                color: Theme.colors.inputText
                placeholderTextColor: Theme.colors.textDisabled
                font.family: Theme.fontMono
                font.pointSize: Theme.metrics.fontSizeBase
                background: Rectangle {
                    color: Theme.colors.inputFill
                    border.color: folderNameField.activeFocus
                                  ? Theme.colors.inputFocusedBorder
                                  : Theme.colors.inputBorder
                    border.width: 1
                    radius: 0
                }
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                Item { Layout.fillWidth: true }
                PanelButton {
                    text: qsTr("Cancel")
                    onClicked: newFolderDialog.close()
                }
                PanelButton {
                    text: qsTr("Create")
                    baseColor: Theme.colors.buttonPrimaryBg
                    labelColor: Theme.colors.buttonPrimaryFg
                    onClicked: {
                        session._handle_create_folder(folderNameField.text)
                        folderNameField.text = ""
                        newFolderDialog.close()
                    }
                }
            }
        }
        onOpened: folderNameField.forceActiveFocus()
    }

    // ------------------------------------------------------------------
    //  Delete folder dialog
    // ------------------------------------------------------------------

    Dialog {
        id: deleteFolderDialog
        anchors.centerIn: Overlay.overlay
        modal: true
        focus: true
        width: 340
        padding: 12
        background: Rectangle {
            color: Theme.colors.surfaceBg
            border.color: Theme.colors.borderDefault
            border.width: 1
            radius: 0
        }
        contentItem: ColumnLayout {
            spacing: 10
            Text {
                Layout.fillWidth: true
                text: qsTr("Delete folder \"") + panel.pendingDeleteFolder
                      + qsTr("\"? Sessions will be unlinked but not deleted.")
                color: Theme.colors.textPrimary
                font.family: Theme.fontMono
                font.pointSize: Theme.metrics.fontSizeBase
                wrapMode: Text.WordWrap
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                Item { Layout.fillWidth: true }
                PanelButton {
                    text: qsTr("Cancel")
                    onClicked: deleteFolderDialog.close()
                }
                PanelButton {
                    text: qsTr("Delete")
                    baseColor: Theme.colors.accentRed
                    labelColor: Theme.colors.pageBg
                    onClicked: {
                        session._handle_delete_folder(panel.pendingDeleteFolder)
                        deleteFolderDialog.close()
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------------
    //  Controller signals
    // ------------------------------------------------------------------

    Connections {
        target: session
        function onNew_folder_requested() {
            folderNameField.text = ""
            newFolderDialog.open()
        }
    }
}
