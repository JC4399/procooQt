import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"
import "../cards"

// Automation page: a fuzzy-search field on top and a scrolling list of
// automation task cards. Browse/edit only; all state lives in the controller.
Rectangle {
    id: panel

    color: Theme.colors.pageBg

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // --------------------------------------------------------------
        //  Search bar
        // --------------------------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 44
            color: Theme.colors.surfaceBg
            border.color: Theme.colors.borderDefault
            border.width: 1
            radius: 0

            TextField {
                id: searchField

                anchors.fill: parent
                anchors.margins: 6
                placeholderText: qsTr("Search automations...")
                placeholderTextColor: Theme.colors.textDisabled
                text: automation.searchText
                color: Theme.colors.inputText
                font.family: Theme.fontMono
                font.pointSize: Theme.metrics.fontSizeBase
                selectByMouse: true

                background: Rectangle {
                    color: Theme.colors.inputFill
                    border.color: searchField.activeFocus
                                  ? Theme.colors.inputFocusedBorder
                                  : Theme.colors.inputBorder
                    border.width: 1
                    radius: 0
                }

                onTextChanged: automation._handle_search_changed(text)
            }
        }

        // --------------------------------------------------------------
        //  Task cards
        // --------------------------------------------------------------
        ListView {
            id: list

            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 8
            topMargin: 10
            bottomMargin: 10
            leftMargin: 10
            rightMargin: 10
            model: automation.automation_model

            delegate: AutomationCard {
                width: list.width - 20
                path: model.path
                name: model.name
                description: model.description
                scheduleText: model.schedule_text
                enabled: model.enabled
                lastRun: model.last_run

                onToggleRequested: function (path, enabled) {
                    automation._handle_toggle(path, enabled)
                }
                onEditRequested: function (path) {
                    automation._handle_edit(path)
                }
            }
        }
    }

    Text {
        anchors.centerIn: parent
        visible: automation.automation_model.count === 0
        text: qsTr("No automations found.")
        color: Theme.colors.textDisabled
        font.family: Theme.fontMono
        font.pointSize: Theme.metrics.fontSizeBase
    }
}
