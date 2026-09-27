import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

import "../components"
import "../cards"

// Separate top-level notification history window: a search field on top and a
// paged list of past notifications below (20 per page, loading more when the
// list is scrolled to the bottom). Hidden at startup; shown from the
// notification page's "View history" action.
Window {
    id: historyWindow

    visible: false
    title: qsTr("Notification History")
    width: 720
    height: 640
    minimumWidth: 420
    minimumHeight: 320
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
                placeholderText: qsTr("Search history...")
                placeholderTextColor: Theme.colors.textDisabled
                text: notification.historySearch
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

                onTextChanged: notification._handle_history_search(text)
            }
        }

        // --------------------------------------------------------------
        //  Paged notification cards
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
            model: notification.history_model

            onAtYEndChanged: {
                if (atYEnd)
                    notification._handle_load_more()
            }

            delegate: NotificationCard {
                width: list.width - 20
                itemId: model.id
                kind: model.kind
                task: model.task
                message: model.message
                timestamp: model.timestamp
                read: model.read

                onConfirmRequested: function (id) {
                    notification._handle_confirm(id)
                }
                onDebugRequested: function (id) {
                    notification._handle_debug(id)
                }
            }

            footer: Item {
                width: list.width
                implicitHeight: 32
                visible: !notification.historyExhausted

                Text {
                    anchors.centerIn: parent
                    text: qsTr("Loading...")
                    color: Theme.colors.textDisabled
                    font.family: Theme.fontMono
                    font.pointSize: Theme.metrics.fontSizeBase
                }
            }
        }
    }

    Text {
        anchors.centerIn: parent
        visible: notification.history_model.count === 0
        text: qsTr("No notifications.")
        color: Theme.colors.textDisabled
        font.family: Theme.fontMono
        font.pointSize: Theme.metrics.fontSizeBase
    }
}
