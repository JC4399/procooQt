import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

// Editor tab: code editor on the left and a collapsible file tree on the right,
// matching the Flet editor | resize | file-tree order. The editor is read-only
// until Edit is pressed; Save/Cancel/Reload drive the controller slots.
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
        font.pixelSize: Theme.metrics.fontSizeLabelSmall

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
    //  Editor pane
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
                font.pixelSize: Theme.metrics.fontSizeGutter
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
                font.pixelSize: Theme.metrics.fontSizeBody
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
    //  File tree pane
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
}
