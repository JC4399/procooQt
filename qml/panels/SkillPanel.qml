import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

Rectangle {
    id: panel

    color: Theme.colors.surfaceBg
    border.color: Theme.colors.borderDefault
    border.width: 1

    component PanelButton: Button {
        id: control

        property color baseColor: Theme.colors.surfaceBg
        property color labelColor: Theme.colors.textPrimary

        implicitHeight: 26
        implicitWidth: 60
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

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        TabBar {
            id: tabs
            Layout.fillWidth: true
            background: Rectangle { color: Theme.colors.elevatedBg }

            TabButton { text: qsTr("Skills") }
            TabButton { text: qsTr("Editor") }
        }

        StackLayout {
            currentIndex: tabs.currentIndex
            Layout.fillWidth: true
            Layout.fillHeight: true

            // ----------------------------------------------------------
            //  Skills tab
            // ----------------------------------------------------------
            ColumnLayout {
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

                // ------------------------------------------------------
                //  Search row
                // ------------------------------------------------------
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
                        font.pixelSize: Theme.metrics.fontSizeLabelSmall
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

                // ------------------------------------------------------
                //  Skill tree
                // ------------------------------------------------------
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

                // ------------------------------------------------------
                //  Tools header
                // ------------------------------------------------------
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
                        font.pixelSize: Theme.metrics.fontSizeTree
                    }

                    Text {
                        Layout.preferredWidth: 34
                        text: qsTr("Allow")
                        color: Theme.colors.textSecondary
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.metrics.fontSizeGutter
                        horizontalAlignment: Text.AlignHCenter
                    }

                    Text {
                        Layout.preferredWidth: 34
                        text: qsTr("Ask")
                        color: Theme.colors.textSecondary
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.metrics.fontSizeGutter
                        horizontalAlignment: Text.AlignHCenter
                    }

                    Text {
                        Layout.preferredWidth: 34
                        text: qsTr("Block")
                        color: Theme.colors.textSecondary
                        font.family: Theme.fontMono
                        font.pixelSize: Theme.metrics.fontSizeGutter
                        horizontalAlignment: Text.AlignHCenter
                    }
                }

                // ------------------------------------------------------
                //  Tool groups
                // ------------------------------------------------------
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
            }

            // ----------------------------------------------------------
            //  Editor tab (P7 placeholder)
            // ----------------------------------------------------------
            EditorPanel {}
        }
    }
}
