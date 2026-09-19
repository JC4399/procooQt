import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// One row of the flattened file tree: either a collapsible folder header or a
// clickable file entry. Displays a short extension label (or "dir") supplied by
// the model and indents by depth. Emits activated() for both kinds; EditorPanel
// routes folders to expansion and files to the editor.
Rectangle {
    id: node

    property string path: ""
    property string name: ""
    property string icon: ""
    property int depth: 0
    property bool isFolder: false
    property bool selected: false
    property bool expanded: false

    signal activated(string path, bool isFolder)

    implicitHeight: 24
    color: node.selected ? Theme.colors.hoverBg : "transparent"
    border.color: node.selected ? Theme.colors.borderDefault : "transparent"
    border.width: 1
    radius: 0

    MouseArea {
        anchors.fill: parent
        onClicked: node.activated(node.path, node.isFolder)
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 6 + node.depth * 14
        anchors.rightMargin: 6
        spacing: 4

        Text {
            visible: node.isFolder
            text: node.expanded ? "\u25be" : "\u25b8"
            color: Theme.colors.textSecondary
            font.family: Theme.fontMono
            font.pixelSize: Theme.metrics.fontSizeGutter
        }

        Text {
            Layout.preferredWidth: 30
            text: node.icon
            color: node.isFolder ? Theme.colors.accentCyan : Theme.colors.textSecondary
            font.family: Theme.fontMono
            font.pixelSize: Theme.metrics.fontSizeGutter
            elide: Text.ElideRight
        }

        Text {
            Layout.fillWidth: true
            text: node.name
            color: node.selected ? Theme.colors.accentCyan : Theme.colors.textPrimary
            font.family: Theme.fontMono
            font.pixelSize: Theme.metrics.fontSizeTree
            elide: Text.ElideRight
            maximumLineCount: 1
        }
    }
}
