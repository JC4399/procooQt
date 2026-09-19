import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

// Editor window content: a collapsible file tree on the left and a code editor
// on the right, matching the layout of a typical text editor. The editor is
// read-only until Edit is pressed; Save/Cancel/Reload drive the controller
// slots. External file changes and deletions raise a themed conflict dialog
// that asks whether to keep the buffer or take the on-disk state.
SplitView {
    id: editorPanel

    orientation: Qt.Horizontal

    handle: Rectangle {
        implicitWidth: 3
        implicitHeight: 3
        color: SplitHandle.hovered ? Theme.colors.accentCyan : Theme.colors.resizeHandle
    }

    component FlatButton: Button {
        id: control

        property color baseColor: Theme.colors.surfaceBg
        property color labelColor: Theme.colors.textPrimary

        implicitHeight: 26
        implicitWidth: Theme.metrics.buttonWidthMedium
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
            color: control.enabled ? control.labelColor : Theme.colors.textDisabled
            font: control.font
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
    }

    // --------------------------------------------------------------
    //  File tree pane (left)
    // --------------------------------------------------------------
    Rectangle {
        id: fileTreePane
        SplitView.preferredWidth: 220
        SplitView.minimumWidth: 120
        SplitView.maximumWidth: 500
        color: Theme.colors.surfaceBg
        border.color: Theme.colors.borderDefault
        border.width: 1
        radius: 0

        ListView {
            id: fileList
            anchors.fill: parent
            clip: true
            spacing: 0
            model: editor.file_model

            delegate: FileNode {
                width: fileList.width
                path: model.path
                name: model.name
                icon: model.icon
                depth: model.depth
                isFolder: model.is_folder
                selected: model.path === editor.currentFile
                expanded: editor.isFolderExpanded(model.path)
                onActivated: function (path, isFolder) {
                    editor._handle_file_click(path, isFolder)
                }
            }
        }
    }

    // --------------------------------------------------------------
    //  Editor pane (right)
    // --------------------------------------------------------------
    ColumnLayout {
        id: editorPane
        SplitView.fillWidth: true
        SplitView.minimumWidth: 240
        spacing: 0

        RowLayout {
            Layout.fillWidth: true
            Layout.margins: 4
            spacing: 4

            FlatButton {
                text: qsTr("Edit")
                visible: !editor.editing
                baseColor: Theme.colors.buttonPrimaryBg
                labelColor: Theme.colors.buttonPrimaryFg
                enabled: editor.currentFile !== ""
                onClicked: editor._handle_edit()
            }

            FlatButton {
                text: qsTr("Reload")
                visible: editor.currentFile !== ""
                onClicked: editor._handle_reload()
            }

            FlatButton {
                text: qsTr("Save")
                visible: editor.editing
                baseColor: Theme.colors.buttonPrimaryBg
                labelColor: Theme.colors.buttonPrimaryFg
                onClicked: editor._handle_save(codeArea.text)
            }

            FlatButton {
                text: qsTr("Cancel")
                visible: editor.editing
                onClicked: editor._handle_cancel()
            }

            Item { Layout.fillWidth: true }

            Text {
                text: editor.language
                color: Theme.colors.textDisabled
                font.family: Theme.fontMono
                font.pointSize: Theme.metrics.fontSizeBase
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.colors.borderDefault
        }

        ScrollView {
            id: editorScroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            background: Rectangle {
                color: Theme.colors.pageBg
                border.color: Theme.colors.borderDefault
                border.width: 1
                radius: 0
            }

            TextArea {
                id: codeArea
                readOnly: !editor.editing
                textFormat: TextEdit.PlainText
                font.family: Theme.fontMono
                font.pointSize: Theme.metrics.fontSizeBase
                color: Theme.colors.textPrimary
                selectionColor: Theme.colors.accentCyan
                selectedTextColor: Theme.colors.pageBg
                wrapMode: TextEdit.NoWrap
                text: editor.currentText
                selectByMouse: true

                property bool dirty: text !== editor.currentText

                Component.onCompleted: editor.attachHighlighter(codeArea)

                Connections {
                    target: editor
                    // Open/save/reload/cancel all replace the buffer; switching
                    // files mid-edit is blocked in the controller, so only
                    // unsaved edits are preserved.
                    function onCurrentFileChanged() {
                        if (!codeArea.dirty || !editor.editing)
                            codeArea.text = editor.currentText
                    }
                }
            }
        }
    }

    // --------------------------------------------------------------
    //  Conflict dialog (deleted / externally modified file)
    // --------------------------------------------------------------
    Dialog {
        id: conflictDialog

        property string kind: ""
        property string filePath: ""

        anchors.centerIn: Overlay.overlay
        modal: true
        focus: true
        width: 400
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
                text: conflictDialog.kind === "deleted"
                      ? qsTr("File deleted")
                      : qsTr("File changed on disk")
                color: Theme.colors.textPrimary
                font.family: Theme.fontMono
                font.pointSize: Theme.metrics.fontSizeBase
                font.bold: true
                wrapMode: Text.WordWrap
            }

            Text {
                Layout.fillWidth: true
                text: conflictDialog.kind === "deleted"
                      ? qsTr("This file was removed: ")
                        + conflictDialog.filePath
                        + qsTr("\nKeep it by recreating it from the editor, or remove it.")
                      : qsTr("This file was modified outside the editor: ")
                        + conflictDialog.filePath
                        + qsTr("\nKeep the editor content, or discard it and reload.")
                color: Theme.colors.textSecondary
                font.family: Theme.fontMono
                font.pointSize: Theme.metrics.fontSizeBase
                wrapMode: Text.WordWrap
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                Item { Layout.fillWidth: true }

                FlatButton {
                    implicitWidth: 160
                    text: conflictDialog.kind === "deleted"
                          ? qsTr("Keep file")
                          : qsTr("Keep editor content")
                    onClicked: {
                        editor._handle_conflict_keep()
                        conflictDialog.close()
                    }
                }

                FlatButton {
                    implicitWidth: 160
                    text: conflictDialog.kind === "deleted"
                          ? qsTr("Remove file")
                          : qsTr("Discard & reload")
                    baseColor: Theme.colors.accentRed
                    labelColor: Theme.colors.pageBg
                    onClicked: {
                        editor._handle_conflict_discard()
                        conflictDialog.close()
                    }
                }
            }
        }
    }

    Connections {
        target: editor
        function onFile_conflict(kind, path) {
            conflictDialog.kind = kind
            conflictDialog.filePath = path
            conflictDialog.open()
        }
    }
}
