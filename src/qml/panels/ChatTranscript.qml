import QtQuick
import QtQuick.Controls

import "../components"
import "../cards"

// One chat's rendered transcript, kept alive per chat so switching tabs only
// toggles visibility instead of rebuilding every card delegate and rich-text
// layout. The workspace decides which chat ids keep a live transcript; this
// component is purely view-only and binds to its chat's ChatListModel.
Item {
    id: root

    // The chat this transcript renders.
    property string chatId: ""
    // The chat's ChatListModel (stable for the chat's lifetime).
    property var chatModel: null
    // Whether this chat is generating (disables card actions).
    property bool busy: false
    // Whether this chat's cold-build overlay is showing.
    property bool loading: false

    // Non-virtualized so contentHeight is exact; ListView's height estimation
    // was unstable for these variable-height cards.
    Flickable {
        id: chatList
        anchors.fill: parent
        anchors.margins: 8
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        contentWidth: width
        contentHeight: chatColumn.implicitHeight

        // Auto-scroll is the autoScrollToggle's checked state: reaching the
        // bottom activates it (fades the toggle in), scrolling away deactivates
        // it (fades the toggle out).
        function atBottom() {
            return contentY >= Math.max(0, contentHeight - height)
        }

        function scrollToBottom() {
            contentY = Math.max(0, contentHeight - height)
        }

        // Scroll so a card body caret at content y / h is on screen, nudging
        // only when it would otherwise be clipped. Only used while auto-scroll
        // is off; when it is on the caret is disabled instead so the view stays
        // pinned to the newest card.
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
                // Qt exposes no wheel-step knob on Flickable; clamp the manual
                // move so it can never overshoot the true bounds.
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
                model: root.chatModel

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
                            value: !root.busy
                            when: cardLoader.item !== null && model.kind !== "context_banner"
                        }
                        Binding {
                            target: cardLoader.item
                            property: "scrollTarget"
                            value: chatList
                            when: cardLoader.item !== null && model.kind !== "context_banner"
                        }
                        Binding {
                            target: cardLoader.item
                            property: "caretEnabled"
                            value: !autoScrollToggle.checked
                            when: cardLoader.item !== null && model.kind !== "context_banner"
                        }
                    }

                    Connections {
                        target: model.kind !== "context_banner" ? cardLoader.item : null

                        function onDeleteRequested(msgIndex) {
                            chat._handle_delete_turn_for(root.chatId, msgIndex)
                        }

                        function onRegenerateRequested(msgIndex) {
                            chat._handle_regenerate_from_for(root.chatId, msgIndex)
                        }

                        function onCaretMoved(caretY, caretHeight) {
                            if (autoScrollToggle.checked)
                                root.clearCaretFocus()
                            else
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
        onCheckedChanged: {
            if (checked)
                root.clearCaretFocus()
        }
    }

    // Shown while a chat's transcript is being built. The opaque fill hides the
    // partially-built list and the scanner keeps running until the build
    // finishes; on hide the view is pinned to the newest card.
    Rectangle {
        id: loadingOverlay
        anchors.fill: parent
        color: Theme.colors.pageBg
        z: 30

        // Hold briefly after the build finishes so short chats show a clean scan
        // instead of a one-frame flash.
        property bool holdVisible: false
        visible: root.loading || holdVisible

        onVisibleChanged: {
            if (visible) {
                holdVisible = true
                minShowTimer.restart()
            } else {
                // Pin to the newest card once the transcript is built. Re-arm
                // auto-scroll so the debounced contentHeight handler keeps
                // following any late delegate layout, and defer the immediate
                // scroll one frame so the Repeater has realized the final batch.
                autoScrollToggle.activateWithFade()
                Qt.callLater(chatList.scrollToBottom)
            }
        }

        Timer {
            id: minShowTimer
            interval: 200
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

    // ------------------------------------------------------------------
    //  Public helpers
    // ------------------------------------------------------------------

    // Auto-scroll owns the viewport while enabled, so any body caret must yield.
    function clearCaretFocus() {
        chatList.forceActiveFocus(Qt.OtherFocusReason)
    }

    // A freshly created transcript starts pinned to the newest card. Cached
    // transcripts keep their previous scroll position.
    Component.onCompleted: {
        autoScrollToggle.activateWithFade()
        Qt.callLater(chatList.scrollToBottom)
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
