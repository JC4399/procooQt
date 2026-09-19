import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// System context banner: a collapsible header plus structured sections. The
// normal scheme is neutral; delta banners use the orange accent. Sections are
// supplied as JSON (``sectionsJson``) from the ChatListModel role so QML stays
// view-only. Body height is animated on collapse/expand via a NumberAnimation.
Rectangle {
    id: banner

    property string kind: ""
    property string title: ""
    property string subtitle: ""
    property string bodyHtml: ""
    property string tokenText: ""
    property string mode: ""
    property bool isPending: false
    property string sectionsJson: ""
    property bool isDelta: false
    property bool bodyCollapsed: false
    property int padTop: 8
    property int padBottom: 8

    property var sections: sectionsJson.length > 0 ? JSON.parse(sectionsJson) : []

    function bgColor() {
        return isDelta ? Theme.colors.contextBannerDeltaBg : Theme.colors.contextBannerBg
    }

    function borderColor() {
        return isDelta ? Theme.colors.contextBannerDeltaBorder
                       : Theme.colors.contextBannerBorder
    }

    implicitHeight: layout.implicitHeight
    color: bgColor()
    border.color: borderColor()
    border.width: 1
    radius: Theme.metrics.contextBannerRadius

    ColumnLayout {
        id: layout
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        spacing: 0

        // ----------------------------------------------------------
        //  Header row + divider
        // ----------------------------------------------------------
        Rectangle {
            id: header
            Layout.fillWidth: true
            implicitHeight: headerRow.implicitHeight + 8
            color: "transparent"

            RowLayout {
                id: headerRow
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 6

                Text {
                    text: banner.bodyCollapsed ? "\u25b8" : "\u25be"
                    color: Theme.colors.textSecondary
                    font.family: Theme.fontMono
                    font.pointSize: Theme.metrics.fontSizeBase
                }

                Text {
                    text: banner.title
                    color: Theme.colors.textPrimary
                    font.family: Theme.fontMono
                    font.pointSize: Theme.metrics.fontSizeBase
                    font.bold: true
                }

                Item { Layout.fillWidth: true }

                Text {
                    text: qsTr("%1 section(s)").arg(banner.sections.length)
                    color: Theme.colors.textSecondary
                    font.family: Theme.fontMono
                    font.pointSize: Theme.metrics.fontSizeBase
                }
            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 1
                color: Theme.colors.cardHeaderDivider
            }

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: banner.bodyCollapsed = !banner.bodyCollapsed
            }
        }

        // ----------------------------------------------------------
        //  Collapsible sections (animated height)
        // ----------------------------------------------------------
        Item {
            id: bodyHost
            Layout.fillWidth: true
            Layout.preferredHeight: bodyHeight
            clip: true

            property real bodyHeight: banner.bodyCollapsed ? 0 : (body.implicitHeight + 12)

            Behavior on bodyHeight {
                NumberAnimation {
                    duration: 160
                    easing.type: Easing.InOutQuad
                }
            }

            Column {
                id: body
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                anchors.topMargin: 6
                spacing: 6

                Repeater {
                    model: banner.sections

                    delegate: Column {
                        width: body.width
                        spacing: 2

                        Text {
                            visible: modelData.header !== ""
                            width: parent.width
                            text: modelData.header
                            color: Theme.colors.textPrimary
                            font.family: Theme.fontMono
                            font.pointSize: Theme.metrics.fontSizeBase
                            font.bold: true
                            wrapMode: Text.Wrap
                        }

                        Repeater {
                            model: modelData.content

                            delegate: Text {
                                width: parent.width
                                text: modelData
                                color: Theme.colors.textSecondary
                                font.family: Theme.fontMono
                                font.pointSize: Theme.metrics.fontSizeBase
                                wrapMode: Text.Wrap
                            }
                        }
                    }
                }
            }
        }
    }
}
