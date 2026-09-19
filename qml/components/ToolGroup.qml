import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// One tool row within a skill group. The first tool of each skill also renders
// the group header (skill display name). Emits the new mode when a radio is picked.
Rectangle {
    id: group

    property string toolName: ""
    property string skillPath: ""
    property string skillDisplayName: ""
    property string description: ""
    property string mode: "ask"
    property bool isGroupStart: false

    signal modeSelected(string toolName, string mode)

    implicitHeight: content.implicitHeight
    color: "transparent"
    border.color: "transparent"
    border.width: 0
    radius: 0

    component FlatRadio: RadioButton {
        id: control

        property color accent: Theme.colors.accentCyan

        implicitWidth: 34
        implicitHeight: 20

        indicator: Rectangle {
            implicitWidth: 12
            implicitHeight: 12
            anchors.centerIn: parent
            color: "transparent"
            border.color: control.checked ? control.accent : Theme.colors.borderStrong
            border.width: 1
            radius: 2

            Rectangle {
                anchors.centerIn: parent
                visible: control.checked
                width: 6
                height: 6
                color: control.accent
                radius: 1
            }
        }

        contentItem: Item {}
    }

    ButtonGroup { id: modeGroup }

    Column {
        id: content
        width: group.width

        Rectangle {
            visible: group.isGroupStart
            width: parent.width
            height: 24
            color: Theme.colors.surfaceBg
            border.color: Theme.colors.borderLight
            border.width: 1
            radius: 0

            Text {
                anchors.left: parent.left
                anchors.leftMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                text: group.skillDisplayName
                color: Theme.colors.textSecondary
                font.family: Theme.fontMono
                font.pixelSize: Theme.metrics.fontSizeTree
                elide: Text.ElideRight
            }
        }

        RowLayout {
            width: parent.width
            height: 24
            spacing: 2

            Text {
                Layout.fillWidth: true
                leftPadding: 16
                text: group.toolName
                color: Theme.colors.textPrimary
                font.family: Theme.fontMono
                font.pixelSize: Theme.metrics.fontSizeTree
                elide: Text.ElideRight
                maximumLineCount: 1
                verticalAlignment: Text.AlignVCenter
            }

            FlatRadio {
                accent: Theme.colors.chipAllowFg
                checked: group.mode === "allow"
                ButtonGroup.group: modeGroup
                onClicked: group.modeSelected(group.toolName, "allow")
            }

            FlatRadio {
                accent: Theme.colors.chipAskFg
                checked: group.mode === "ask"
                ButtonGroup.group: modeGroup
                onClicked: group.modeSelected(group.toolName, "ask")
            }

            FlatRadio {
                accent: Theme.colors.chipBlockFg
                checked: group.mode === "block"
                ButtonGroup.group: modeGroup
                onClicked: group.modeSelected(group.toolName, "block")
            }
        }
    }
}
