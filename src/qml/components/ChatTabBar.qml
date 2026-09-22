import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

// Chat tab bar for one chat panel: a blue "+" at the left creates a chat and the
// tabs to its right select/close/drag chats. Tab widths shrink as more tabs open,
// like a web browser. Dragging is tracked manually (window coordinates) so the
// owning workspace can render a ghost and decide split vs. move on release.
Rectangle {
    id: bar

    // Panel index this tab bar belongs to.
    property int panelIndex: 0
    // The ChatPanelModel's tab model.
    property var tabModel: null

    // Chat id queued for deletion, shown by the confirmation dialog.
    property string pendingDeleteChatId: ""

    signal newChatRequested()
    signal tabClicked(string chatId)
    signal dragStarted(string chatId, string title, real sceneX, real sceneY)
    signal dragMoved(real sceneX, real sceneY)
    signal dragEnded(string chatId, real sceneX, real sceneY)
    signal dragCanceled()

    implicitHeight: 30
    color: Theme.colors.surfaceBg
    border.color: Theme.colors.borderDefault
    border.width: 1
    radius: 0

    component TabButton: Button {
        id: control

        implicitWidth: 24
        implicitHeight: 22
        font.family: Theme.fontMono
        font.pointSize: Theme.metrics.fontSizeBase

        background: Rectangle {
            color: control.down ? Theme.colors.hoverBg : Theme.colors.buttonPrimaryBg
            radius: 0
            border.color: Theme.colors.borderDefault
            border.width: 1
        }

        contentItem: Text {
            text: control.text
            color: Theme.colors.buttonPrimaryFg
            font: control.font
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 4
        anchors.rightMargin: 4
        spacing: 4

        TabButton {
            text: qsTr("+")
            onClicked: bar.newChatRequested()
        }

        Flickable {
            id: tabScroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentWidth: tabRow.implicitWidth
            contentHeight: height
            boundsBehavior: Flickable.StopAtBounds

            function tabWidth() {
                const count = tabRepeater.count
                if (count <= 0)
                    return 0
                const avail = Math.max(0, width - (count - 1) * tabRow.spacing)
                return Math.max(80, Math.min(220, avail / count))
            }

            Row {
                id: tabRow
                height: tabScroll.height
                spacing: 2

                Repeater {
                    id: tabRepeater
                    model: bar.tabModel

                    delegate: Rectangle {
                        id: tab
                        width: tabScroll.tabWidth()
                        height: tabRow.height
                        color: model.is_active ? Theme.colors.chatSelectedBg
                                               : (tabArea.containsMouse ? Theme.colors.hoverBg
                                                                        : Theme.colors.surfaceBg)
                        border.color: model.is_active ? Theme.colors.borderStrong
                                                      : Theme.colors.borderLight
                        border.width: 1
                        radius: 0

                        property real pressX: 0
                        property real pressY: 0
                        property bool dragging: false

                        function scenePoint(mx, my) {
                            var root = Window.window ? Window.window.contentItem : null
                            return tabArea.mapToItem(root, mx, my)
                        }

                        MouseArea {
                            id: tabArea
                            anchors.fill: parent
                            hoverEnabled: true
                            acceptedButtons: Qt.LeftButton
                            // Keep the enclosing Flickable from stealing the drag.
                            preventStealing: true

                            onPressed: function (mouse) {
                                tab.pressX = mouse.x
                                tab.pressY = mouse.y
                            }
                            onPositionChanged: function (mouse) {
                                if (!pressed)
                                    return
                                if (!tab.dragging
                                        && Math.hypot(mouse.x - tab.pressX,
                                                      mouse.y - tab.pressY) > 6) {
                                    tab.dragging = true
                                    var p0 = tab.scenePoint(mouse.x, mouse.y)
                                    bar.dragStarted(model.chat_id, model.title, p0.x, p0.y)
                                }
                                if (tab.dragging) {
                                    var p = tab.scenePoint(mouse.x, mouse.y)
                                    bar.dragMoved(p.x, p.y)
                                }
                            }
                            onReleased: function (mouse) {
                                if (tab.dragging) {
                                    var p = tab.scenePoint(mouse.x, mouse.y)
                                    bar.dragEnded(model.chat_id, p.x, p.y)
                                    tab.dragging = false
                                } else {
                                    bar.tabClicked(model.chat_id)
                                }
                            }
                            onCanceled: {
                                tab.dragging = false
                                bar.dragCanceled()
                            }
                        }

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 6
                            anchors.rightMargin: 4
                            spacing: 4

                            Rectangle {
                                Layout.alignment: Qt.AlignVCenter
                                width: 8
                                height: 8
                                radius: Theme.metrics.statusDotRadius
                                color: session.statusColor(model.status)

                                SequentialAnimation on opacity {
                                    running: model.is_blinking
                                    loops: Animation.Infinite
                                    NumberAnimation {
                                        to: 0.2; duration: 300; easing.type: Easing.InOutQuad
                                    }
                                    NumberAnimation {
                                        to: 1.0; duration: 300; easing.type: Easing.InOutQuad
                                    }
                                }
                            }

                            Text {
                                Layout.fillWidth: true
                                Layout.alignment: Qt.AlignVCenter
                                text: model.title
                                color: Theme.colors.textPrimary
                                font.family: Theme.fontMono
                                font.pointSize: Theme.metrics.fontSizeBase
                                elide: Text.ElideRight
                                maximumLineCount: 1
                            }

                            Rectangle {
                                Layout.alignment: Qt.AlignVCenter
                                width: 16
                                height: 16
                                color: closeArea.containsMouse ? Theme.colors.hoverBg : "transparent"
                                radius: 0

                                Text {
                                    anchors.centerIn: parent
                                    text: "\u00d7"
                                    color: Theme.colors.textSecondary
                                    font.family: Theme.fontMono
                                    font.pointSize: Theme.metrics.fontSizeBase
                                }

                                MouseArea {
                                    id: closeArea
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    onClicked: {
                                        bar.pendingDeleteChatId = model.chat_id
                                        deleteChatDialog.open()
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------------
    //  Delete chat confirmation
    // ------------------------------------------------------------------

    Dialog {
        id: deleteChatDialog
        anchors.centerIn: Overlay.overlay
        modal: true
        focus: true
        width: 340
        padding: 12
        background: Rectangle {
            color: Theme.colors.surfaceBg
            border.color: Theme.colors.borderDefault
            border.width: 1
            radius: 0
        }
        contentItem: ColumnLayout {
            spacing: 10
            Text {
                Layout.fillWidth: true
                text: qsTr("Delete this chat and its history?")
                color: Theme.colors.textPrimary
                font.family: Theme.fontMono
                font.pointSize: Theme.metrics.fontSizeBase
                wrapMode: Text.WordWrap
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                Item { Layout.fillWidth: true }
                FlatDialogButton {
                    text: qsTr("Cancel")
                    onClicked: deleteChatDialog.close()
                }
                FlatDialogButton {
                    text: qsTr("Delete")
                    baseColor: Theme.colors.buttonPrimaryBg
                    labelColor: Theme.colors.buttonPrimaryFg
                    onClicked: {
                        session._handle_delete_chat(bar.pendingDeleteChatId)
                        deleteChatDialog.close()
                    }
                }
            }
        }
    }

    component FlatDialogButton: Button {
        id: control

        property color baseColor: Theme.colors.surfaceBg
        property color labelColor: Theme.colors.textPrimary

        implicitHeight: 26
        implicitWidth: 72
        font.family: Theme.fontMono
        font.pointSize: Theme.metrics.fontSizeBase

        background: Rectangle {
            color: control.down ? Theme.colors.hoverBg : control.baseColor
            radius: 0
            border.color: Theme.colors.borderDefault
            border.width: 1
        }

        contentItem: Text {
            text: control.text
            color: control.labelColor
            font: control.font
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
    }
}
