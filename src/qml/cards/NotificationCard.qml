import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

// One notification card. The outer border encodes the card's nature (grey for
// success logs, amber for info, red for errors). Info cards offer Confirm;
// error cards offer Confirm and Debug (open the source automation). Log cards
// have no action because they are auto-acknowledged when the page opens.
Rectangle {
    id: card

    property string itemId: ""
    property string kind: "log"
    property string task: ""
    property string message: ""
    property string timestamp: ""
    property bool read: false

    signal confirmRequested(string itemId)
    signal debugRequested(string itemId)

    function borderColor() {
        if (card.kind === "error")
            return Theme.colors.notificationErrorBorder
        if (card.kind === "info")
            return Theme.colors.notificationInfoBorder
        return Theme.colors.notificationLogBorder
    }

    function kindLabel() {
        if (card.kind === "error")
            return qsTr("Error")
        if (card.kind === "info")
            return qsTr("Info")
        return qsTr("Log")
    }

    implicitHeight: layout.implicitHeight + 20
    color: Theme.colors.notificationBg
    border.color: borderColor()
    border.width: 1
    radius: Theme.metrics.cardRadius
    opacity: card.read ? 0.75 : 1.0

    component FieldLabel: Text {
        color: Theme.colors.textSecondary
        font.family: Theme.fontMono
        font.pointSize: Theme.metrics.fontSizeBase
    }

    ColumnLayout {
        id: layout
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 10
        spacing: 4

        // ----------------------------------------------------------
        //  Time + kind badge + task row
        // ----------------------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            FieldLabel {
                text: card.timestamp
            }

            Rectangle {
                implicitWidth: kindText.implicitWidth + 10
                implicitHeight: kindText.implicitHeight + 4
                color: card.borderColor()
                radius: 0

                Text {
                    id: kindText
                    anchors.centerIn: parent
                    text: card.kindLabel()
                    color: Theme.colors.badgeFg
                    font.family: Theme.fontMono
                    font.pointSize: Theme.metrics.fontSizeBase
                    font.bold: true
                }
            }

            Text {
                Layout.fillWidth: true
                text: card.task
                color: Theme.colors.textPrimary
                font.family: Theme.fontMono
                font.pointSize: Theme.metrics.fontSizeBase
                font.bold: true
                elide: Text.ElideRight
            }
        }

        // ----------------------------------------------------------
        //  Result row
        // ----------------------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            FieldLabel {
                text: qsTr("Result")
                Layout.preferredWidth: 70
            }

            TextEdit {
                Layout.fillWidth: true
                Layout.preferredHeight: contentHeight
                text: card.message
                color: Theme.colors.textSecondary
                font.family: Theme.fontMono
                font.pointSize: Theme.metrics.fontSizeBase
                readOnly: true
                textFormat: TextEdit.PlainText
                wrapMode: TextEdit.Wrap
                selectByMouse: true
            }
        }

        // ----------------------------------------------------------
        //  Actions (info / error only)
        // ----------------------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            visible: card.kind === "info" || card.kind === "error"

            Item { Layout.fillWidth: true }

            FlatButton {
                implicitWidth: 90
                text: qsTr("Confirm")
                onClicked: card.confirmRequested(card.itemId)
            }

            FlatButton {
                implicitWidth: 90
                visible: card.kind === "error"
                text: qsTr("Debug")
                baseColor: Theme.colors.buttonPrimaryBg
                labelColor: Theme.colors.buttonPrimaryFg
                onClicked: card.debugRequested(card.itemId)
            }
        }
    }
}
