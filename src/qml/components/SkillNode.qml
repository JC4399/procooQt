import QtQuick
import QtQuick.Layouts

// One row of the flattened skill tree: either a collapsible folder header or a
// skill row with an activated checkbox and a tool-count badge.
Rectangle {
    id: node

    property string path: ""
    property string name: ""
    property string description: ""
    property int depth: 0
    property bool isFolder: false
    property bool activated: false
    property bool hasTools: false
    property bool expanded: false
    property int skillCount: 0
    property int selectedCount: 0

    signal activatedToggled(string path, bool checked)
    signal folderToggled(string path, bool expanded)

    implicitHeight: 28
    color: node.isFolder ? Theme.colors.elevatedBg : "transparent"
    border.color: node.isFolder ? Theme.colors.borderLight : "transparent"
    border.width: node.isFolder ? 1 : 0
    radius: 0

    MouseArea {
        anchors.fill: parent
        enabled: node.isFolder
        onClicked: node.folderToggled(node.path, !node.expanded)
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 6 + node.depth * 16
        anchors.rightMargin: 11
        spacing: 6

        // Folder header
        Text {
            visible: node.isFolder
            text: node.expanded ? "\u25bc" : "\u25b6"
            color: Theme.colors.textSecondary
            font.family: Theme.fontMono
            font.pointSize: Theme.metrics.fontSizeBase
        }

        Text {
            visible: node.isFolder
            text: node.name
            color: Theme.colors.textPrimary
            font.family: Theme.fontMono
            font.pointSize: Theme.metrics.fontSizeBase
            elide: Text.ElideRight
            Layout.maximumWidth: node.width * 0.5
        }

        Text {
            visible: node.isFolder
            text: node.skillCount + " skill(s)"
            color: Theme.colors.textDisabled
            font.family: Theme.fontMono
            font.pointSize: Theme.metrics.fontSizeBase
        }

        Text {
            visible: node.isFolder
            text: node.selectedCount + " selected"
            color: Theme.colors.accentCyan
            font.family: Theme.fontMono
            font.pointSize: Theme.metrics.fontSizeBase
        }

        // Skill name + badge
        Text {
            visible: !node.isFolder
            Layout.fillWidth: true
            text: node.name
            color: Theme.colors.textPrimary
            font.family: Theme.fontMono
            font.pointSize: Theme.metrics.fontSizeBase
            elide: Text.ElideRight
            maximumLineCount: 1
        }

        Rectangle {
            visible: !node.isFolder && node.hasTools
            implicitWidth: toolsLabel.implicitWidth + 8
            implicitHeight: 16
            color: Theme.colors.chipToolsBg
            border.color: Theme.colors.borderDefault
            border.width: 1
            radius: 0

            Text {
                id: toolsLabel
                anchors.centerIn: parent
                text: qsTr("tools")
                color: Theme.colors.chipToolsFg
                font.family: Theme.fontMono
                font.pointSize: Theme.metrics.fontSizeBase
            }
        }

        Item { visible: node.isFolder; Layout.fillWidth: true }

        FlatCheckBox {
            visible: !node.isFolder
            accent: Theme.colors.accentCyan
            checked: node.activated
            onClicked: node.activatedToggled(node.path, checked)
        }
    }
}
