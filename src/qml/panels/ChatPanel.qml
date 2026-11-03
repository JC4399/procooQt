import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

Rectangle {
    id: panel

    // The ChatPanelModel supplied by the workspace, and this panel's fixed slot.
    property var panelModel: null
    property int slot: 0

    // Split-drop hint from the workspace: "" (none), "left", "right", or "move".
    property string dropHint: ""

    // Height of the tab bar region (used by the workspace to detect "move" drops).
    readonly property real tabBarHeight: 30

    signal openEditorRequested()
    signal dragStarted(string chatId, string title, real sceneX, real sceneY)
    signal dragMoved(real sceneX, real sceneY)
    signal dragEnded(string chatId, real sceneX, real sceneY)
    signal dragCanceled()

    color: Theme.colors.pageBg
    border.color: Theme.colors.borderDefault
    border.width: 1

    // ------------------------------------------------------------------
    //  Shared action button
    // ------------------------------------------------------------------

    component ActionButton: Button {
        id: control

        property color baseColor: Theme.colors.surfaceBg
        property color labelColor: Theme.colors.textPrimary

        implicitHeight: 28
        implicitWidth: Theme.metrics.buttonWidthMedium
        font.family: Theme.fontMono
        font.pointSize: Theme.metrics.fontSizeBase

        background: Rectangle {
            color: control.down ? Theme.colors.hoverBg : control.baseColor
            radius: Theme.metrics.buttonRadius
            border.color: Theme.colors.borderDefault
            border.width: 1
        }

        contentItem: Text {
            text: control.text
            color: control.enabled ? control.labelColor : Theme.colors.textDisabled
            font: control.font
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ----------------------------------------------------------
        //  Chat tab bar
        // ----------------------------------------------------------
        ChatTabBar {
            Layout.fillWidth: true
            panelIndex: panel.slot
            tabModel: panel.panelModel ? panel.panelModel.tabModel : null
            onNewChatRequested: session._handle_new_chat(panel.slot)
            onTabClicked: function (chatId) {
                session._handle_panel_activate(panel.slot, chatId)
            }
            onDragStarted: function (chatId, title, sceneX, sceneY) {
                panel.dragStarted(chatId, title, sceneX, sceneY)
            }
            onDragMoved: function (sceneX, sceneY) {
                panel.dragMoved(sceneX, sceneY)
            }
            onDragEnded: function (chatId, sceneX, sceneY) {
                panel.dragEnded(chatId, sceneX, sceneY)
            }
            onDragCanceled: panel.dragCanceled()
        }

        // ----------------------------------------------------------
        //  Chat transcript host (one cached transcript per chat)
        // ----------------------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.rightMargin: skillDock.railWidth
            color: Theme.colors.pageBg
            border.color: Theme.colors.chatBorder
            border.width: 1
            radius: Theme.metrics.chatContainerRadius

            Item {
                id: transcriptHost
                anchors.fill: parent

                Repeater {
                    model: panel.panelModel ? panel.panelModel.transcriptModel : null

                    delegate: ChatTranscript {
                        anchors.fill: parent
                        visible: model.chat_id === (panel.panelModel
                                                    ? panel.panelModel.activeChatId : "")
                        chatId: model.chat_id
                        chatModel: panel.panelModel
                                   ? panel.panelModel.chatModelFor(model.chat_id) : null
                        busy: panel.panelModel
                              && panel.panelModel.activeChatId === model.chat_id
                              ? panel.panelModel.busy : false
                        loading: panel.panelModel
                                 && panel.panelModel.activeChatId === model.chat_id
                                 ? panel.panelModel.loading : false
                    }
                }
            }
        }

        // ----------------------------------------------------------
        //  Approval bar
        // ----------------------------------------------------------
        ApprovalBar {
            Layout.fillWidth: true
            Layout.rightMargin: skillDock.railWidth
            chatId: panel.panelModel ? panel.panelModel.activeChatId : ""
            approvalVisible: panel.panelModel ? panel.panelModel.approvalVisible : false
            approvalText: panel.panelModel ? panel.panelModel.approvalText : ""
        }

        // ----------------------------------------------------------
        //  Combined config + token bar (above the input)
        // ----------------------------------------------------------
        ConfigTokenBar {
            Layout.fillWidth: true
            Layout.rightMargin: skillDock.railWidth
                activatedCount: panel.panelModel ? panel.panelModel.activatedCount : 0
            allowCount: panel.panelModel ? panel.panelModel.allowCount : 0
            askCount: panel.panelModel ? panel.panelModel.askCount : 0
            blockCount: panel.panelModel ? panel.panelModel.blockCount : 0
            inputTokens: panel.panelModel ? panel.panelModel.inputTokens : 0
            outputTokens: panel.panelModel ? panel.panelModel.outputTokens : 0
            modelName: panel.panelModel ? panel.panelModel.modelName : ""
        }

        // ----------------------------------------------------------
        //  Input row
        // ----------------------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 8
            Layout.topMargin: 8
            Layout.bottomMargin: 8
            Layout.rightMargin: skillDock.railWidth + (8)
            spacing: 8

            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(140, Math.max(72, input.contentHeight + 12))

                ScrollView {
                    id: inputScroll
                    anchors.fill: parent
                    clip: true

                    background: Rectangle {
                        color: Theme.colors.inputFill
                        border.color: input.activeFocus
                                      ? Theme.colors.inputFocusedBorder
                                      : Theme.colors.inputBorder
                        border.width: 1
                        radius: 0
                    }

                    // Wheel scrolling still works; the right-side bar is gone.
                    ScrollBar.vertical.policy: ScrollBar.AlwaysOff

                    TextArea {
                        id: input
                        width: inputScroll.availableWidth
                        placeholderText: qsTr("Type a message...")
                        wrapMode: TextArea.Wrap
                        enabled: !(panel.panelModel && panel.panelModel.busy)
                        color: Theme.colors.inputText
                        placeholderTextColor: Theme.colors.textDisabled
                        font.family: Theme.fontMono
                        font.pointSize: Theme.metrics.fontSizeBase
                        background: null

                        Keys.onPressed: function (event) {
                            if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                                if (event.modifiers & Qt.ShiftModifier) {
                                    event.accepted = false
                                } else {
                                    event.accepted = true
                                    if (!enterLockToggle.checked)
                                        panel.submit()
                                }
                            }
                        }
                    }
                }

                // Enter lock: hidden until hovered, stays visible while checked.
                // When checked, Enter never sends; the Send button is the only
                // way out. Shift+Enter still inserts a line break either way.
                FlatCheckBox {
                    id: enterLockToggle
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    anchors.margins: 6
                    z: 2
                    padding: 4
                    hoverEnabled: true
                    opacity: (checked || hovered) ? 1 : 0
                    Behavior on opacity {
                        NumberAnimation {
                            duration: 120
                        }
                    }
                }
            }

            ColumnLayout {
                spacing: 6

                ActionButton {
                    text: qsTr("Send")
                    visible: !(panel.panelModel && panel.panelModel.busy)
                    baseColor: Theme.colors.buttonPrimaryBg
                    labelColor: Theme.colors.buttonPrimaryFg
                    onClicked: panel.submit()
                }

                ActionButton {
                    text: qsTr("Stop")
                    visible: panel.panelModel ? panel.panelModel.busy : false
                    baseColor: Theme.colors.buttonPrimaryBg
                    labelColor: Theme.colors.buttonPrimaryFg
                    onClicked: chat._handle_stop_for(panel.activeChatId())
                }

                ActionButton {
                    text: qsTr("Regenerate")
                    visible: !(panel.panelModel && panel.panelModel.busy)
                    onClicked: chat._handle_regenerate_for(panel.activeChatId())
                }
            }
        }
    }

    // ------------------------------------------------------------------
    //  Split drop indicator
    // ------------------------------------------------------------------

    Rectangle {
        id: splitOverlay
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: parent.width / 2
        x: panel.dropHint === "left" ? 0 : parent.width / 2
        z: 40
        visible: panel.dropHint === "left" || panel.dropHint === "right"
        color: Theme.colors.splitDropFill
        border.color: Theme.colors.splitDropBorder
        border.width: 1
    }

    // ------------------------------------------------------------------
    //  Per-chat skill dock (collapsed by default; spans the panel body)
    // ------------------------------------------------------------------

    SkillDock {
        id: skillDock
        anchors.top: parent.top
        anchors.topMargin: panel.tabBarHeight
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        z: 35
        chatId: panel.activeChatId()
        onOpenEditorRequested: panel.openEditorRequested()
    }

    // ------------------------------------------------------------------
    //  Input submission
    // ------------------------------------------------------------------

    function activeChatId() {
        return panel.panelModel ? panel.panelModel.activeChatId : ""
    }

    // Return the transcript currently shown for this panel's active chat.
    function activeTranscript() {
        for (let i = 0; i < transcriptHost.children.length; i++) {
            const child = transcriptHost.children[i]
            if (child.chatId !== undefined && child.visible)
                return child
        }
        return null
    }

    // While streaming with auto-scroll on, auto-scroll owns the viewport, so any
    // body caret must yield.
    function clearCaretFocus() {
        const transcript = panel.activeTranscript()
        if (transcript)
            transcript.clearCaretFocus()
    }

    function submit() {
        if (!input.text.trim())
            return
        chat._handle_send_for(panel.activeChatId(), input.text)
        input.text = ""
    }
}
