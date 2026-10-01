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

    // The primary window owns the shared editor / history windows and quits the
    // app when closed; closing a secondary window only closes that window.
    onClosing: Qt.quit()

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
        onOpenEditorRequested: {
            editorWindow.show()
            editorWindow.requestActivate()
        }
    }

    AutomationPanel {
        anchors.top: titleBar.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        visible: root.activeContent === "automation"
    }

    NotificationPanel {
        id: notificationPanel
        anchors.top: titleBar.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        visible: root.activeContent === "notification"
        onViewHistoryRequested: {
            notification._handle_view_history()
            historyWindow.show()
            historyWindow.requestActivate()
        }
    }

    EditorWindow {
        id: editorWindow
    }

    // Opening a file from outside the workspace (e.g. notification Debug)
    // requests the editor window to be shown.
    Connections {
        target: editor
        function onEditor_open_requested() {
            editorWindow.show()
            editorWindow.requestActivate()
        }
    }

    // Secondary windows route editor / history requests here (the singletons
    // live in the primary window).
    Connections {
        target: windows
        function onShow_editor_requested() {
            editorWindow.show()
            editorWindow.requestActivate()
        }
        function onShow_history_requested() {
            notification._handle_view_history()
            historyWindow.show()
            historyWindow.requestActivate()
        }
    }

    NotificationHistoryWindow {
        id: historyWindow
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
