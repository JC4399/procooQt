import QtQuick
import QtQuick.Window

import "../panels"

// Standalone top-level code editor window bound to the shared `editor`
// controller. Instantiated on demand by the Python `WindowManager` (exposed to
// QML as `windows`) via `windows.show_editor()`; never created at startup.
// Visibility is reported to the controller so file/content conflicts are only
// prompted for while the window is actually showing.
Window {
    id: editorWindow

    visible: false
    title: qsTr("Editor")
    width: 900
    height: 640
    minimumWidth: 480
    minimumHeight: 320
    color: Theme.colors.pageBg

    onVisibleChanged: editor._handle_window_visibility(visible)

    EditorPanel {
        anchors.fill: parent
    }
}
