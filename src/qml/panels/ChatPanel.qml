import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"
import "../cards"

Rectangle {
    id: panel

    // The ChatPanelModel supplied by the workspace, and this panel's index.
    property var panelModel: null
    property int panelIndex: 0

    // Split-drop hint from the workspace: "" (none), "left", "right", or "move".
    property string dropHint: ""

    // Height of the tab bar region (used by the workspace to detect "move" drops).
    readonly property real tabBarHeight: 30

    // Mirrors the active chat id so a genuine switch (not every panel-model
    // update, whose notify signal is shared) can re-arm auto-scroll.
    property string trackedChatId: panelModel ? panelModel.activeChatId : ""

    onTrackedChatIdChanged: {
        if (autoScrollToggle)
            autoScrollToggle.activateWithFade()
    }

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
            panelIndex: panel.panelIndex
            tabModel: panel.panelModel ? panel.panelModel.tabModel : null
            onNewChatRequested: session._handle_new_chat(panel.panelIndex)
            onTabClicked: function (chatId) {
                session._handle_panel_activate(panel.panelIndex, chatId)
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
        //  Chat list
        // ----------------------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.rightMargin: skillDock.railWidth
            color: Theme.colors.pageBg
            border.color: Theme.colors.chatBorder
            border.width: 1
            radius: Theme.metrics.chatContainerRadius

            // Non-virtualized so contentHeight is exact; ListView's height
            // estimation was unstable for these variable-height cards.
            Flickable {
                id: chatList
                anchors.fill: parent
                anchors.margins: 8
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                contentWidth: width
                contentHeight: chatColumn.implicitHeight

                // Auto-scroll is the autoScrollToggle's checked state: reaching
                // the bottom activates it (fades the toggle in), scrolling away
                // deactivates it (fades the toggle out).
                function atBottom() {
                    return contentY >= Math.max(0, contentHeight - height)
                }

                function scrollToBottom() {
                    contentY = Math.max(0, contentHeight - height)
                }

                // Scroll so a card body caret at content y / h is on screen,
                // nudging only when it would otherwise be clipped. Auto-scroll
                // reacts to the resulting contentY change (deactivating when we
                // move away from the bottom).
                function ensureVisible(y, h) {
                    const margin = 8
                    const maxY = Math.max(0, contentHeight - height)
                    if (y - margin < contentY)
                        contentY = Math.min(maxY, y - margin)
                    else if (y + h + margin > contentY + height)
                        contentY = Math.min(maxY, y + h + margin - height)
                }

                function scheduleScroll() {
                    if (autoScrollToggle.checked)
                        scrollDebounce.restart()
                }

                onContentYChanged: {
                    if (atBottom()) {
                        if (!autoScrollToggle.checked)
                            autoScrollToggle.activateWithFade()
                    } else if (autoScrollToggle.checked) {
                        autoScrollToggle.deactivateWithFade()
                    }
                }

                onContentHeightChanged: scheduleScroll()
                onMovementEnded: scheduleScroll()

                Timer {
                    id: scrollDebounce
                    interval: 30
                    repeat: false
                    onTriggered: {
                        if (!chatList.moving && !chatList.flicking
                                && autoScrollToggle.checked)
                            chatList.scrollToBottom()
                    }
                }

                ScrollBar.vertical: ScrollBar {
                    id: chatScrollBar
                    policy: ScrollBar.AsNeeded

                    background: Rectangle {
                        color: "transparent"
                    }

                    contentItem: Rectangle {
                        implicitWidth: 6
                        radius: 0
                        color: Theme.colors.borderStrong
                        opacity: chatScrollBar.size < 1.0 ? 1 : 0
                    }
                }

                WheelHandler {
                    onWheel: function (event) {
                        const pixel = event.pixelDelta.y
                        const step = pixel !== 0
                                     ? pixel
                                     : (event.angleDelta.y / 120) * Theme.metrics.wheelScrollStep
                        // Qt exposes no wheel-step knob on Flickable; clamp the
                        // manual move so it can never overshoot the true bounds.
                        const maxY = Math.max(0, chatList.contentHeight - chatList.height)
                        chatList.contentY = Math.max(0, Math.min(maxY, chatList.contentY - step))
                        event.accepted = true
                    }
                }

                Column {
                    id: chatColumn
                    width: chatList.width
                    spacing: 6

                    Repeater {
                        model: panel.panelModel ? panel.panelModel.chatModel : null

                        delegate: Item {
                            width: chatColumn.width
                            height: cardLoader.item
                                    ? cardLoader.item.implicitHeight
                                      + cardLoader.item.padTop
                                      + cardLoader.item.padBottom
                                    : 0

                            Loader {
                                id: cardLoader
                                width: parent.width
                                y: cardLoader.item ? cardLoader.item.padTop : 0

                                sourceComponent: {
                                    switch (model.kind) {
                                    case "user":
                                        return userCardComponent
                                    case "thinking":
                                        return thinkingCardComponent
                                    case "response":
                                        return responseCardComponent
                                    case "tool_call":
                                        return toolCallCardComponent
                                    case "tool_result":
                                        return toolResultCardComponent
                                    case "context_banner":
                                        return contextBannerComponent
                                    case "waiting":
                                        return waitingCardComponent
                                    default:
                                        return null
                                    }
                                }

                                Binding {
                                    target: cardLoader.item
                                    property: "bodyHtml"
                                    value: model.body_html
                                    when: cardLoader.item !== null
                                }
                                Binding {
                                    target: cardLoader.item
                                    property: "bodyTailHtml"
                                    value: model.body_tail_html
                                    when: cardLoader.item !== null && model.kind !== "context_banner"
                                }
                                Binding {
                                    target: cardLoader.item
                                    property: "tokenText"
                                    value: model.token_text
                                    when: cardLoader.item !== null
                                }
                                Binding {
                                    target: cardLoader.item
                                    property: "mode"
                                    value: model.mode
                                    when: cardLoader.item !== null
                                }
                                Binding {
                                    target: cardLoader.item
                                    property: "isPending"
                                    value: model.is_pending
                                    when: cardLoader.item !== null
                                }
                                Binding {
                                    target: cardLoader.item
                                    property: "subtitle"
                                    value: model.tool_name
                                    when: cardLoader.item !== null
                                }
                                Binding {
                                    target: cardLoader.item
                                    property: "title"
                                    value: model.title
                                    when: cardLoader.item !== null && model.kind === "context_banner"
                                }
                                Binding {
                                    target: cardLoader.item
                                    property: "sectionsJson"
                                    value: model.sections
                                    when: cardLoader.item !== null && model.kind === "context_banner"
                                }
                                Binding {
                                    target: cardLoader.item
                                    property: "isDelta"
                                    value: model.is_delta
                                    when: cardLoader.item !== null && model.kind === "context_banner"
                                }
                                Binding {
                                    target: cardLoader.item
                                    property: "bodyCollapsed"
                                    value: model.collapsed
                                    when: cardLoader.item !== null
                                }
                                Binding {
                                    target: cardLoader.item
                                    property: "msgIndex"
                                    value: model.msg_index
                                    when: cardLoader.item !== null && model.kind !== "context_banner"
                                }
                                Binding {
                                    target: cardLoader.item
                                    property: "actionsEnabled"
                                    value: !(panel.panelModel && panel.panelModel.busy)
                                    when: cardLoader.item !== null && model.kind !== "context_banner"
                                }
                                Binding {
                                    target: cardLoader.item
                                    property: "scrollTarget"
                                    value: chatList
                                    when: cardLoader.item !== null && model.kind !== "context_banner"
                                }
                            }

                            Connections {
                                target: model.kind !== "context_banner" ? cardLoader.item : null

                                function onDeleteRequested(msgIndex) {
                                    chat._handle_delete_turn_for(panel.activeChatId(), msgIndex)
                                }

                                function onRegenerateRequested(msgIndex) {
                                    chat._handle_regenerate_from_for(panel.activeChatId(), msgIndex)
                                }

                                function onCaretMoved(caretY, caretHeight) {
                                    chatList.ensureVisible(caretY, caretHeight)
                                }
                            }
                        }
                    }
                }
            }

            AutoScrollToggle {
                id: autoScrollToggle
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.margins: 12
                z: 20
                onToggled: {
                    if (checked)
                        chatList.scrollToBottom()
                }
            }

            // Shown while a chat's transcript is being built. The opaque fill
            // hides the partially-built list and the scanner keeps running until
            // the build finishes; on hide the view is pinned to the newest card.
            Rectangle {
                id: loadingOverlay
                anchors.fill: parent
                color: Theme.colors.pageBg
                z: 30

                // Hold briefly after the build finishes so short chats show a
                // clean scan instead of a one-frame flash.
                property bool holdVisible: false
                visible: (panel.panelModel ? panel.panelModel.loading : false) || holdVisible

                onVisibleChanged: {
                    if (visible) {
                        holdVisible = true
                        minShowTimer.restart()
                    } else {
                        // Pin to the newest card once the transcript is built.
                        // Re-arm auto-scroll so the debounced contentHeight
                        // handler keeps following any late delegate layout, and
                        // defer the immediate scroll one frame so the Repeater
                        // has realized the final batch.
                        autoScrollToggle.activateWithFade()
                        Qt.callLater(chatList.scrollToBottom)
                    }
                }

                Timer {
                    id: minShowTimer
                    interval: 400
                    repeat: false
                    onTriggered: loadingOverlay.holdVisible = false
                }

                KnightRiderSpinner {
                    anchors.centerIn: parent
                    running: loadingOverlay.visible
                    baseColor: Theme.colors.accentCyan
                    cells: 10
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
            primaryCount: panel.panelModel ? panel.panelModel.primaryCount : 0
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

    function submit() {
        if (!input.text.trim())
            return
        chat._handle_send_for(panel.activeChatId(), input.text)
        input.text = ""
    }

    // ------------------------------------------------------------------
    //  Card components
    // ------------------------------------------------------------------

    Component {
        id: userCardComponent
        UserCard {}
    }

    Component {
        id: thinkingCardComponent
        ThinkingCard {}
    }

    Component {
        id: responseCardComponent
        ResponseCard {}
    }

    Component {
        id: toolCallCardComponent
        ToolCallCard {}
    }

    Component {
        id: toolResultCardComponent
        ToolResultCard {}
    }

    Component {
        id: contextBannerComponent
        ContextBanner {}
    }

    Component {
        id: waitingCardComponent
        WaitingCard {}
    }
}
