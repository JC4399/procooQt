import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"
import "../cards"

Rectangle {
    id: panel

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
        //  Active config bar
        // ----------------------------------------------------------
        ActiveConfigBar {
            Layout.fillWidth: true
        }

        // ----------------------------------------------------------
        //  Chat list
        // ----------------------------------------------------------
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
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

                // Follow the newest card while the user has not scrolled away.
                // Toggle ON forces follow; OFF follows only while pinned to the end.
                property bool followTail: true
                property bool _autoScrolling: false

                function scrollToBottom() {
                    _autoScrolling = true
                    contentY = Math.max(0, contentHeight - height)
                    _autoScrolling = false
                }

                function scheduleScroll() {
                    if (autoScrollToggle.checked || followTail)
                        scrollDebounce.restart()
                }

                onContentYChanged: {
                    if (!_autoScrolling)
                        followTail = atYEnd
                }

                onContentHeightChanged: scheduleScroll()
                onMovementEnded: scheduleScroll()

                Timer {
                    id: scrollDebounce
                    interval: 30
                    repeat: false
                    onTriggered: {
                        if (!chatList.moving && !chatList.flicking)
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
                        chatList.contentY -= step
                        chatList.returnToBounds()
                        event.accepted = true
                    }
                }

                Column {
                    id: chatColumn
                    width: chatList.width
                    spacing: 6

                    Repeater {
                        model: chat.activeModel

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
                                    when: cardLoader.item !== null && model.kind === "context_banner"
                                }
                            }
                        }
                    }
                }
            }

            BusyIndicator {
                anchors.centerIn: parent
                visible: chat.loading
                running: chat.loading
                implicitWidth: 32
                implicitHeight: 32
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
        }

        // ----------------------------------------------------------
        //  Token bar
        // ----------------------------------------------------------
        TokenBar {
            Layout.fillWidth: true
        }

        // ----------------------------------------------------------
        //  Input row
        // ----------------------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            Layout.margins: 8
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
                    placeholderText: qsTr("Type a message...")
                    wrapMode: TextArea.Wrap
                    enabled: !chat.busy
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
                    visible: !chat.busy
                    baseColor: Theme.colors.buttonPrimaryBg
                    labelColor: Theme.colors.buttonPrimaryFg
                    onClicked: panel.submit()
                }

                ActionButton {
                    text: qsTr("Stop")
                    visible: chat.busy
                    baseColor: Theme.colors.accentRed
                    labelColor: Theme.colors.pageBg
                    onClicked: chat._handle_stop()
                }

                ActionButton {
                    text: qsTr("Regenerate")
                    visible: !chat.busy
                    onClicked: chat._handle_regenerate()
                }
            }
        }
    }

    // ------------------------------------------------------------------
    //  Input submission
    // ------------------------------------------------------------------

    function submit() {
        if (!input.text.trim())
            return
        chat._handle_send(input.text)
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
}
