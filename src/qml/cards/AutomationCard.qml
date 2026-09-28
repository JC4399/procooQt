import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

// One automation task card. Shows the task name, description, and schedule
// (or "Event driven (<event>)" for event automations), an enable toggle at the
// top right, and an Edit button at the bottom right. View-only: the parent
// wires the signals to the automation controller.
Rectangle {
    id: card

    property string path: ""
    property string name: ""
    property string description: ""
    property string scheduleText: ""
    property bool enabled: true
    property string lastRun: ""
    property bool running: false

    signal toggleRequested(string path, bool enabled)
    signal editRequested(string path)
    signal runRequested(string path)

    implicitHeight: layout.implicitHeight + 20
    color: Theme.colors.surfaceBg
    border.color: Theme.colors.borderDefault
    border.width: 1
    radius: Theme.metrics.cardRadius

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
        //  Task row + enable toggle
        // ----------------------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            FieldLabel {
                text: qsTr("Task")
                Layout.preferredWidth: 82
            }

            Text {
                Layout.fillWidth: true
                text: card.name
                color: Theme.colors.textPrimary
                font.family: Theme.fontMono
                font.pointSize: Theme.metrics.fontSizeBase
                font.bold: true
                elide: Text.ElideRight
            }

            FieldLabel {
                text: card.enabled ? qsTr("on") : qsTr("off")
            }

            FlatCheckBox {
                checked: card.enabled
                onToggled: card.toggleRequested(card.path, checked)
            }
        }

        // ----------------------------------------------------------
        //  Description row
        // ----------------------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            FieldLabel {
                text: qsTr("Description")
                Layout.preferredWidth: 82
            }

            Text {
                Layout.fillWidth: true
                text: card.description
                color: Theme.colors.textSecondary
                font.family: Theme.fontMono
                font.pointSize: Theme.metrics.fontSizeBase
                wrapMode: Text.WordWrap
            }
        }

        // ----------------------------------------------------------
        //  Schedule row
        // ----------------------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            FieldLabel {
                text: qsTr("Schedule")
                Layout.preferredWidth: 82
            }

            Text {
                Layout.fillWidth: true
                text: card.scheduleText
                color: Theme.colors.textSecondary
                font.family: Theme.fontMono
                font.pointSize: Theme.metrics.fontSizeBase
                elide: Text.ElideRight
            }
        }

        // ----------------------------------------------------------
        //  Actions
        // ----------------------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            FieldLabel {
                visible: card.lastRun !== ""
                text: qsTr("Last run: %1").arg(card.lastRun)
                Layout.fillWidth: true
                elide: Text.ElideRight
            }

            Item { Layout.fillWidth: true }

            KnightRiderSpinner {
                visible: card.running
                running: card.running
                cells: 5
                baseColor: Theme.colors.accentGreen
                Layout.alignment: Qt.AlignVCenter
            }

            FlatButton {
                implicitWidth: 90
                text: card.running ? qsTr("Running...") : qsTr("Run now")
                enabled: !card.running
                onClicked: card.runRequested(card.path)
            }

            FlatButton {
                implicitWidth: 90
                text: qsTr("Edit")
                onClicked: card.editRequested(card.path)
            }
        }
    }
}
