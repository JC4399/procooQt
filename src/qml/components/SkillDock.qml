import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

// Per-panel skill/tool dock. Collapsed it is a thin rail at the panel's right
// edge with an arrow; expanded it covers the panel's chat area with its own
// collapse rail on the left. Collapsed by default; one instance per chat panel.
Item {
    id: dock

    property bool expanded: false
    property string chatId: ""
    // Width of the expanded panel (user-adjustable via the left edge).
    property real expandedWidth: 380

    // Width of the thin rail shown when collapsed (also reserved in the layout).
    readonly property real railWidth: 18

    signal openEditorRequested()

    onExpandedChanged: {
        if (expanded && chatId !== "")
            skill._handle_chat_activated(chatId)
    }
    onChatIdChanged: {
        if (expanded && chatId !== "")
            skill._handle_chat_activated(chatId)
    }

    // ------------------------------------------------------------------
    //  Shared button
    // ------------------------------------------------------------------

    component PanelButton: Button {
        id: control

        property color baseColor: Theme.colors.surfaceBg
        property color labelColor: Theme.colors.textPrimary

        implicitHeight: 26
        implicitWidth: 60
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

    // ------------------------------------------------------------------
    //  Collapsed rail (right edge)
    // ------------------------------------------------------------------

    Rectangle {
        id: collapsedRail
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: dock.railWidth
        visible: !dock.expanded
        color: Theme.colors.surfaceBg
        border.color: Theme.colors.borderDefault
        border.width: 1
        radius: 0

        Text {
            anchors.centerIn: parent
            text: "\u25c0"
            color: Theme.colors.textSecondary
            font.family: Theme.fontMono
            font.pointSize: Theme.metrics.fontSizeBase
        }

        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            onClicked: dock.expanded = true
        }
    }

    // ------------------------------------------------------------------
    //  Expanded panel
    // ------------------------------------------------------------------

    Rectangle {
        id: expandedPanel
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: Math.max(220, Math.min((dock.parent ? dock.parent.width - 40 : 800),
                                      dock.expandedWidth))
        visible: dock.expanded
        color: Theme.colors.surfaceBg
        border.color: Theme.colors.borderDefault
        border.width: 1
        radius: 0
        z: 1

        // Collapse rail on the panel's left edge (also the resize handle).
        Rectangle {
            id: expandedRail
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: dock.railWidth
            color: Theme.colors.elevatedBg
            border.color: Theme.colors.borderDefault
            border.width: 1
            radius: 0

            Text {
                anchors.centerIn: parent
                text: "\u25b6"
                color: Theme.colors.textSecondary
                font.family: Theme.fontMono
                font.pointSize: Theme.metrics.fontSizeBase
            }

            MouseArea {
                id: railArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.SizeHorCursor

                property real startWidth: 0
                property real startSceneX: 0
                property bool moved: false

                function sceneX(mx) {
                    var root = Window.window ? Window.window.contentItem : null
                    return railArea.mapToItem(root, mx, 0).x
                }

                onPressed: function (mouse) {
                    railArea.startWidth = dock.expandedWidth
                    railArea.startSceneX = railArea.sceneX(mouse.x)
                    railArea.moved = false
                }
                onPositionChanged: function (mouse) {
                    if (!pressed)
                        return
                    var delta = railArea.startSceneX - railArea.sceneX(mouse.x)
                    if (Math.abs(delta) > 3)
                        railArea.moved = true
                    if (railArea.moved) {
                        var maxWidth = (dock.parent ? dock.parent.width - 40 : 800)
                        dock.expandedWidth = Math.max(220, Math.min(maxWidth,
                                                                     railArea.startWidth + delta))
                    }
                }
                onReleased: {
                    if (!railArea.moved)
                        dock.expanded = false
                }
                onCanceled: railArea.moved = false
            }
        }

        ColumnLayout {
            anchors.left: expandedRail.right
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            spacing: 0

            PresetBar {
                id: presetBar
                Layout.fillWidth: true
                presetNames: skill.presetNames
                onLoadRequested: function (name) { skill._handle_load_preset(name) }
                onSaveRequested: function (name) {
                    skill.presetName = name
                    skill._handle_save_preset()
                }
                onDeleteRequested: function (name) { skill._handle_delete_preset(name) }
            }

            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: Theme.colors.borderDefault
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.margins: 6
                spacing: 6

                TextField {
                    id: searchField
                    Layout.fillWidth: true
                    implicitHeight: 26
                    placeholderText: qsTr("Search...")
                    color: Theme.colors.inputText
                    placeholderTextColor: Theme.colors.textDisabled
                    font.family: Theme.fontMono
                    font.pointSize: Theme.metrics.fontSizeBase
                    background: Rectangle {
                        color: Theme.colors.inputFill
                        border.color: searchField.activeFocus
                                      ? Theme.colors.inputFocusedBorder
                                      : Theme.colors.inputBorder
                        border.width: 1
                        radius: 0
                    }
                    onTextChanged: skill._handle_search_changed(text)
                }

                PanelButton {
                    implicitWidth: 26
                    text: qsTr("\u00d7")
                    visible: searchField.text.length > 0
                    onClicked: {
                        searchField.text = ""
                        skill._handle_clear_search()
                    }
                }
            }

            ListView {
                id: skillList
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredHeight: 420
                clip: true
                spacing: 0
                model: skill.skill_model

                delegate: Item {
                    width: skillList.width
                    height: 28

                    SkillNode {
                        anchors.fill: parent
                        path: model.path
                        name: model.name
                        description: model.description
                        depth: model.depth
                        isFolder: model.is_folder
                        primary: model.primary
                        secondary: model.secondary
                        hasTools: model.has_tools
                        expanded: model.expanded
                        skillCount: model.skill_count
                        selectedCount: model.selected_count
                        onPrimaryToggled: function (path, checked) {
                            skill._handle_skill_toggle(path, "primary", checked)
                        }
                        onSecondaryToggled: function (path, checked) {
                            skill._handle_skill_toggle(path, "secondary", checked)
                        }
                        onFolderToggled: function (path, expanded) {
                            skill._handle_folder_toggle(path, expanded)
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: Theme.colors.borderDefault
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 8
                Layout.rightMargin: 8
                height: 24
                spacing: 2

                Text {
                    Layout.fillWidth: true
                    text: qsTr("Tools")
                    color: Theme.colors.textPrimary
                    font.family: Theme.fontMono
                    font.bold: true
                    font.pointSize: Theme.metrics.fontSizeBase
                }

                Text {
                    Layout.preferredWidth: 34
                    text: qsTr("Allow")
                    color: Theme.colors.textSecondary
                    font.family: Theme.fontMono
                    font.pointSize: Theme.metrics.fontSizeBase
                    horizontalAlignment: Text.AlignHCenter
                }

                Text {
                    Layout.preferredWidth: 34
                    text: qsTr("Ask")
                    color: Theme.colors.textSecondary
                    font.family: Theme.fontMono
                    font.pointSize: Theme.metrics.fontSizeBase
                    horizontalAlignment: Text.AlignHCenter
                }

                Text {
                    Layout.preferredWidth: 34
                    text: qsTr("Block")
                    color: Theme.colors.textSecondary
                    font.family: Theme.fontMono
                    font.pointSize: Theme.metrics.fontSizeBase
                    horizontalAlignment: Text.AlignHCenter
                }
            }

            Flickable {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredHeight: 220
                clip: true
                contentHeight: toolColumn.implicitHeight
                boundsBehavior: Flickable.StopAtBounds

                Column {
                    id: toolColumn
                    width: parent.width

                    Repeater {
                        model: skill.tool_model

                        delegate: ToolGroup {
                            width: toolColumn.width
                            toolName: model.tool_name
                            skillPath: model.skill_path
                            skillDisplayName: model.skill_display_name
                            description: model.description
                            mode: model.mode
                            isGroupStart: model.is_group_start
                            onModeSelected: function (toolName, mode) {
                                skill._handle_tool_mode_change(toolName, mode)
                            }
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: Theme.colors.borderDefault
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.margins: 6
                spacing: 6

                PanelButton {
                    Layout.fillWidth: true
                    text: qsTr("Open Editor")
                    baseColor: Theme.colors.buttonPrimaryBg
                    labelColor: Theme.colors.buttonPrimaryFg
                    onClicked: dock.openEditorRequested()
                }
            }
        }
    }
}
