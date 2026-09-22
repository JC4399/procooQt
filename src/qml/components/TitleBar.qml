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
