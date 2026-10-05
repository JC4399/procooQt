import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"
import "../cards"

// Full chat panel for the editor window. Mirrors ChatPanel.qml (same streaming
// cards, auto-scroll, token bar, and input) but bound to the shared `editorChat`
// controller, which runs a real chat through ChatController. The open file is
// injected as context by the controller.
Rectangle {
    id: panel

    color: Theme.colors.pageBg
    border.color: Theme.colors.borderDefault
    border.width: 1
    radius: 0

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
        //  Header
        // ----------------------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 32
            color: Theme.colors.elevatedBg
            radius: 0

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 6

                Text {
                    text: qsTr("Editor Chat")
                    color: Theme.colors.textPrimary
                    font.family: Theme.fontMono
                    font.pointSize: Theme.metrics.fontSizeBase
                    font.bold: true
                }

                Item { Layout.fillWidth: true }

                ActionButton {
                    implicitWidth: 70
                    text: qsTr("Clear")
                    onClicked: editorChat._handle_clear()
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.colors.borderDefault
        }

        // ----------------------------------------------------------
        //  Chat list
        // ----------------------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.rightMargin: editorSkillDock.railWidth
            color: Theme.colors.pageBg
            border.color: Theme.colors.chatBorder
            border.width: 1
            radius: Theme.metrics.chatContainerRadius

            Flickable {
                id: chatList
                anchors.fill: parent
                anchors.margins: 8
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                contentWidth: width
                contentHeight: chatColumn.implicitHeight

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
                        model: editorChat.chat_model

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
                                    value: !editorChat.busy
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
                                target: cardLoader.item

                                function onDeleteRequested(msgIndex) {
                                    editorChat._handle_delete_turn(msgIndex)
                                }

                                function onRegenerateRequested(msgIndex) {
                                    editorChat._handle_regenerate_from(msgIndex)
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
        }

        // ----------------------------------------------------------
        //  Approval bar
        // ----------------------------------------------------------
        ApprovalBar {
            Layout.fillWidth: true
            Layout.rightMargin: editorSkillDock.railWidth
            chatId: "editor-chat"
            approvalVisible: editorChat.approvalVisible
            approvalText: editorChat.approvalText
        }

        // ----------------------------------------------------------
        //  Token bar
        // ----------------------------------------------------------
        ConfigTokenBar {
            Layout.fillWidth: true
            Layout.rightMargin: editorSkillDock.railWidth
            primaryCount: editorChat.primaryCount
            allowCount: editorChat.allowCount
            askCount: editorChat.askCount
            blockCount: editorChat.blockCount
            inputTokens: editorChat.inputTokens
            outputTokens: editorChat.outputTokens
            modelName: editorChat.modelName
        }

        // ----------------------------------------------------------
        //  Input
        // ----------------------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 8
            Layout.topMargin: 8
            Layout.bottomMargin: 8
            Layout.rightMargin: editorSkillDock.railWidth + 8
            spacing: 8

            ScrollView {
                id: inputScroll
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(140, Math.max(72, input.contentHeight + 12))
                clip: true

                background: Rectangle {
                    color: Theme.colors.inputFill
                    border.color: input.activeFocus
                                  ? Theme.colors.inputFocusedBorder
                                  : Theme.colors.inputBorder
                    border.width: 1
                    radius: 0
                }

                ScrollBar.vertical: ScrollBar {
                    id: inputBar
                    parent: inputScroll
                    x: inputScroll.mirrored ? 0 : inputScroll.width - width
                    y: inputScroll.topPadding
                    height: inputScroll.availableHeight
                    policy: ScrollBar.AsNeeded

                    background: Rectangle {
                        color: Theme.colors.inputFill
                    }

                    contentItem: Rectangle {
                        implicitWidth: 6
                        implicitHeight: 6
                        radius: 0
                        color: Theme.colors.borderStrong
                        opacity: inputBar.size < 1.0 ? 1 : 0
                    }
                }

                TextArea {
                    id: input
                    width: inputScroll.availableWidth
                    placeholderText: qsTr("Ask to edit this file...")
                    wrapMode: TextArea.Wrap
                    enabled: !editorChat.busy
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
                                panel.submit()
                            }
                        }
                    }
                }
            }

            ColumnLayout {
                spacing: 6

                ActionButton {
                    text: qsTr("Send")
                    visible: !editorChat.busy
                    baseColor: Theme.colors.buttonPrimaryBg
                    labelColor: Theme.colors.buttonPrimaryFg
                    onClicked: panel.submit()
                }

                ActionButton {
                    text: qsTr("Stop")
                    visible: editorChat.busy
                    baseColor: Theme.colors.buttonPrimaryBg
                    labelColor: Theme.colors.buttonPrimaryFg
                    onClicked: editorChat._handle_stop()
                }

                ActionButton {
                    text: qsTr("Regenerate")
                    visible: !editorChat.busy
                    onClicked: editorChat._handle_regenerate()
                }
            }
        }
    }

    // ------------------------------------------------------------------
    //  Per-chat skill dock (collapsed by default; spans the panel body)
    // ------------------------------------------------------------------
    SkillDock {
        id: editorSkillDock
        anchors.top: parent.top
        anchors.topMargin: 33
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        z: 35
        chatId: "editor-chat"
    }

    // ------------------------------------------------------------------
    //  Input submission
    // ------------------------------------------------------------------
    function submit() {
        if (!input.text.trim())
            return
        editorChat._handle_send(input.text)
        input.text = ""
    }

    // ------------------------------------------------------------------
    //  Card components (shared with ChatPanel)
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
