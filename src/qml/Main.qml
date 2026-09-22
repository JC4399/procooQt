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

    SplitWorkspace {
        id: workspace
        anchors.top: titleBar.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        onOpenEditorRequested: {
            editorWindow.show()
            editorWindow.requestActivate()
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
