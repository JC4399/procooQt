import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

import "panels"
import "components"
import "windows"

ApplicationWindow {
    id: root

    visible: true
    width: 1440
    height: 900
    minimumWidth: 1024
    minimumHeight: 640
    title: qsTr("ProcooQt")
    color: Theme.colors.pageBg
    flags: Qt.Window | Qt.FramelessWindowHint

    TitleBar {
        id: titleBar
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        title: root.title
    }

    SplitView {
        id: splitView
        anchors.top: titleBar.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        orientation: Qt.Horizontal

        handle: Rectangle {
            implicitWidth: 2
            implicitHeight: 2
            color: SplitHandle.hovered ? Theme.colors.accentCyan : Theme.colors.resizeHandle
        }

        // Progressive defaults: panel widths track the window width until the
        // user drags a handle, after which their explicit sizes win.
        SessionPanel {
            id: sessionPanel
            SplitView.preferredWidth: Math.max(220, Math.min(320, root.width * 0.20))
            SplitView.minimumWidth: 200
            SplitView.maximumWidth: 480
        }

        ChatPanel {
            id: chatPanel
            SplitView.fillWidth: true
            SplitView.minimumWidth: 420
        }

        SkillPanel {
            id: skillPanel
            SplitView.preferredWidth: Math.max(320, Math.min(560, root.width * 0.30))
            SplitView.minimumWidth: 280
            SplitView.maximumWidth: 680
            onOpenEditorRequested: {
                editorWindow.show()
                editorWindow.requestActivate()
            }
        }
    }

    EditorWindow {
        id: editorWindow
    }

    ToastHost {
        id: toastHost
        anchors.top: titleBar.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        notifier: toasts
    }
}
