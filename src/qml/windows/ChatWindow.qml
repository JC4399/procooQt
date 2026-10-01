import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

import "../panels"
import "../components"

// Secondary per-session window. Instantiated by the Python `WindowManager` with
// a private QML context that supplies this window's own `session`, `chat`, and
// `skill`; `Theme`, `toasts`, `editor`, `automation`, `notification`, and
// `windows` come from the shared root context. The editor and notification
// history windows are singletons owned by the primary window, so requests here
// are routed through `windows` instead of showing local instances.
ApplicationWindow {
    id: root

    visible: true
    width: 1200
    height: 800
    minimumWidth: 900
    minimumHeight: 600
    title: qsTr("ProcooQt \u2014 ") + (session.activeSessionName || "")
    color: Theme.colors.pageBg
    flags: Qt.Window | Qt.FramelessWindowHint

    // Active central content view: "chat", "automation", or "notification".
    property string activeContent: "chat"

    TitleBar {
        id: titleBar
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        title: root.title
        activeContent: root.activeContent
        logCount: notification.logCount
        infoCount: notification.infoCount
        errorCount: notification.errorCount
        onContentSelected: function (content) {
            root.activeContent = content
        }
    }

    SplitWorkspace {
        id: workspace
        anchors.top: titleBar.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        visible: root.activeContent === "chat"
        onOpenEditorRequested: windows.show_editor()
    }

    AutomationPanel {
        anchors.top: titleBar.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        visible: root.activeContent === "automation"
    }

    NotificationPanel {
        anchors.top: titleBar.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        visible: root.activeContent === "notification"
        onViewHistoryRequested: {
            notification._handle_view_history()
            windows.show_history()
        }
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
