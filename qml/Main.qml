import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "panels"
import "components"

ApplicationWindow {
    id: root

    visible: true
    width: 1440
    height: 900
    minimumWidth: 1024
    minimumHeight: 640
    title: qsTr("Procoo Agent Assistant")
    color: Theme.colors.pageBg

    SplitView {
        id: splitView
        anchors.fill: parent
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
        }
    }

    ToastHost {
        id: toastHost
        anchors.fill: parent
        notifier: toasts
    }
}
