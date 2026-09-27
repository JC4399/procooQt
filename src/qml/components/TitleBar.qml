import QtQuick
import QtQuick.Window

// Frameless window title bar: a static logo at the left, the app name centred,
// and flat minimise / maximise / close controls at the right. The empty bar
// area is also the drag surface for moving the window via ``startSystemMove``.
// View-only: it reads the enclosing ``Window`` through the ``Window.window``
// attached property and never touches backend objects.
Rectangle {
    id: titleBar

    property string title: ""
    property url logoSource: Qt.resolvedUrl("../../../assets/logos/logo.png")

    // Active central content view: "chat", "automation", or "notification".
    property string activeContent: "chat"
    // Unread notification counts shown as badges next to the bell.
    property int logCount: 0
    property int infoCount: 0
    property int errorCount: 0

    signal contentSelected(string content)

    readonly property var window: Window.window

    implicitHeight: Theme.metrics.titleBarHeight
    color: Theme.colors.surfaceBg

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 1
        color: Theme.colors.borderDefault
    }

    // Drag surface — declared first so the logo and buttons stay on top.
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton
        onPressed: {
            if (titleBar.window)
                titleBar.window.startSystemMove()
        }
        onDoubleClicked: {
            if (!titleBar.window)
                return
            if (titleBar.window.visibility === Window.Maximized)
                titleBar.window.showNormal()
            else
                titleBar.window.showMaximized()
        }
    }

    Image {
        id: logo
        anchors.left: parent.left
        anchors.leftMargin: 10
        anchors.verticalCenter: parent.verticalCenter
        width: Theme.metrics.titleBarLogoSize
        height: Theme.metrics.titleBarLogoSize
        source: titleBar.logoSource
        fillMode: Image.PreserveAspectFit
        smooth: true
    }

    // ------------------------------------------------------------------
    //  Content tabs: Chat | Automation | (bell + unread badges)
    // ------------------------------------------------------------------
    Row {
        id: contentTabs
        anchors.left: logo.right
        anchors.leftMargin: 14
        anchors.verticalCenter: parent.verticalCenter
        spacing: 2

        component ContentTab: Rectangle {
            id: tab

            property string label: ""
            property string content: ""

            readonly property bool active: titleBar.activeContent === tab.content

            implicitWidth: tabText.implicitWidth + 22
            implicitHeight: 22
            color: tabArea.containsMouse || tab.active ? Theme.colors.hoverBg : "transparent"
            radius: 0

            Text {
                id: tabText
                anchors.centerIn: parent
                text: tab.label
                color: tab.active ? Theme.colors.textPrimary : Theme.colors.textSecondary
                font.family: Theme.fontMono
                font.pointSize: Theme.metrics.fontSizeBase
                font.bold: tab.active
            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 2
                color: tab.active ? Theme.colors.contentTabActive : "transparent"
            }

            MouseArea {
                id: tabArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: titleBar.contentSelected(tab.content)
            }
        }

        component UnreadBadge: Rectangle {
            id: badge

            property int count: 0
            property color bgColor: Theme.colors.badgeLogBg

            visible: count > 0
            implicitWidth: Math.max(14, badgeText.implicitWidth + 8)
            implicitHeight: 14
            radius: height / 2
            color: badge.bgColor

            Text {
                id: badgeText
                anchors.centerIn: parent
                text: badge.count > 99 ? "99+" : badge.count
                color: Theme.colors.badgeFg
                font.family: Theme.fontMono
                font.pointSize: Theme.metrics.fontSizeBase - 2
                font.bold: true
            }
        }

        ContentTab {
            label: qsTr("Chat")
            content: "chat"
        }

        ContentTab {
            label: qsTr("Automation")
            content: "automation"
        }

        Rectangle {
            id: bell

            readonly property bool active: titleBar.activeContent === "notification"

            implicitWidth: bellRow.implicitWidth + 20
            implicitHeight: 22
            color: bellArea.containsMouse || bell.active ? Theme.colors.hoverBg : "transparent"
            radius: 0

            Row {
                id: bellRow
                anchors.centerIn: parent
                spacing: 4

                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: qsTr("Notification")
                    color: bell.active ? Theme.colors.textPrimary : Theme.colors.textSecondary
                    font.family: Theme.fontMono
                    font.pointSize: Theme.metrics.fontSizeBase
                    font.bold: bell.active
                }

                UnreadBadge {
                    anchors.verticalCenter: parent.verticalCenter
                    count: titleBar.logCount
                    bgColor: Theme.colors.badgeLogBg
                }

                UnreadBadge {
                    anchors.verticalCenter: parent.verticalCenter
                    count: titleBar.infoCount
                    bgColor: Theme.colors.badgeInfoBg
                }

                UnreadBadge {
                    anchors.verticalCenter: parent.verticalCenter
                    count: titleBar.errorCount
                    bgColor: Theme.colors.badgeErrorBg
                }
            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 2
                color: bell.active ? Theme.colors.contentTabActive : "transparent"
            }

            MouseArea {
                id: bellArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: titleBar.contentSelected("notification")
            }
        }
    }

    SessionSelector {
        id: sessionSelector
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.verticalCenter: parent.verticalCenter
    }

    Row {
        id: controls
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom

        TitleBarButton {
            height: controls.height
            glyph: "\u2212"
            onClicked: {
                if (titleBar.window)
                    titleBar.window.showMinimized()
            }
        }

        TitleBarButton {
            height: controls.height
            glyph: titleBar.window
                   && titleBar.window.visibility === Window.Maximized
                   ? "\u2750"
                   : "\u25A1"
            onClicked: {
                if (!titleBar.window)
                    return
                if (titleBar.window.visibility === Window.Maximized)
                    titleBar.window.showNormal()
                else
                    titleBar.window.showMaximized()
            }
        }

        TitleBarButton {
            height: controls.height
            glyph: "\u00D7"
            danger: true
            onClicked: {
                if (titleBar.window)
                    titleBar.window.close()
            }
        }
    }
}
