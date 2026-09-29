import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"
import "../cards"

// Notification page: a scrolling list of notification cards with a "View
// history" action pinned to the bottom. Opening the page marks success logs as
// read (they stay visible, dimmed, until the page is closed); info and error
// cards stay until the user confirms them.
Rectangle {
    id: panel

    color: Theme.colors.pageBg

    signal viewHistoryRequested()

    onVisibleChanged: {
        if (visible)
            notification._handle_page_opened()
        else
            notification._handle_page_closed()
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // --------------------------------------------------------------
        //  Notification cards
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
            model: notification.notification_model

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
        }

        // --------------------------------------------------------------
        //  Bottom bar
        // --------------------------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 44
            color: Theme.colors.surfaceBg
            border.color: Theme.colors.borderDefault
            border.width: 1
            radius: 0

            RowLayout {
                anchors.fill: parent
                anchors.margins: 8
                spacing: 6

                Item { Layout.fillWidth: true }

                FlatButton {
                    text: qsTr("View history")
                    onClicked: panel.viewHistoryRequested()
                }
            }
        }
    }

    Text {
        anchors.centerIn: parent
        visible: notification.notification_model.count === 0
        text: qsTr("No notifications.")
        color: Theme.colors.textDisabled
        font.family: Theme.fontMono
        font.pointSize: Theme.metrics.fontSizeBase
    }
}
