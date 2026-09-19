import QtQuick
import QtQuick.Layouts

Rectangle {
    id: header

    property string folderName: ""
    property int sessionCount: 0
    property bool expanded: false
    property bool dropHovered: false

    signal toggled(bool expanded)
    signal deleteRequested()
    signal dropOnFolder(string sessionId, string folder)

    implicitHeight: 34
    color: Theme.colors.elevatedBg
    border.color: header.dropHovered ? Theme.colors.dragFeedbackBorder
                                     : Theme.colors.borderDefault
    border.width: header.dropHovered ? 2 : 1
    radius: 0

    MouseArea {
        anchors.fill: parent
        onClicked: header.toggled(!header.expanded)
    }

    DropArea {
        anchors.fill: parent
        keys: ["session"]

        onEntered: header.dropHovered = true
        onExited: header.dropHovered = false
        onDropped: function (drop) {
            header.dropHovered = false
            var sessionId = header.sessionIdFromDrop(drop)
            if (sessionId !== "")
                header.dropOnFolder(sessionId, header.folderName)
            drop.acceptProposedAction()
        }
    }

    function sessionIdFromDrop(drop) {
        if (drop.source && drop.source.sessionId !== undefined)
            return drop.source.sessionId
        if (drop.formats && drop.formats.indexOf("text/plain") !== -1)
            return drop.getDataAsString("text/plain")
        return ""
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 8
        anchors.rightMargin: 6
        spacing: 6

        Text {
            text: header.expanded ? "\u25bc" : "\u25b6"
            color: Theme.colors.textSecondary
            font.family: Theme.fontMono
            font.pixelSize: Theme.metrics.fontSizeLabelSmall
        }

        Text {
            Layout.fillWidth: true
            text: header.folderName
            color: Theme.colors.textPrimary
            font.family: Theme.fontMono
            font.pixelSize: Theme.metrics.fontSizeBody
            elide: Text.ElideRight
            maximumLineCount: 1
        }

        Text {
            text: header.sessionCount + " sessions"
            color: Theme.colors.textSecondary
            font.family: Theme.fontMono
            font.pixelSize: Theme.metrics.fontSizeLabelSmall
        }

        Rectangle {
            Layout.alignment: Qt.AlignVCenter
            implicitWidth: 20
            implicitHeight: 20
            color: folderDeleteArea.containsMouse ? Theme.colors.hoverBg : "transparent"
            border.color: Theme.colors.borderDefault
            border.width: 1
            radius: 0

            Text {
                anchors.centerIn: parent
                text: "\u00d7"
                color: Theme.colors.textSecondary
                font.family: Theme.fontMono
                font.pixelSize: Theme.metrics.fontSizeBody
            }

            MouseArea {
                id: folderDeleteArea
                anchors.fill: parent
                hoverEnabled: true
                onClicked: header.deleteRequested()
            }
        }
    }
}
