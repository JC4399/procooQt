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
        font.pixelSize: Theme.metrics.fontSizeLabelSmall

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

            ListView {
                id: chatList
                anchors.fill: parent
                anchors.margins: 8
                clip: true
                spacing: 6
                model: chat.activeModel
                cacheBuffer: 500

                onCountChanged: {
                    if (atYEnd || contentHeight <= height)
                        positionViewAtEnd()
                }

                delegate: Item {
                    width: chatList.width
                    height: cardLoader.item ? cardLoader.item.implicitHeight : 0

                    Loader {
                        id: cardLoader
                        width: parent.width

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

            TextArea {
                id: input
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(140, Math.max(72, contentHeight + 12))
                placeholderText: qsTr("Type a message...")
                wrapMode: TextArea.Wrap
                enabled: !chat.busy
                color: Theme.colors.inputText
                placeholderTextColor: Theme.colors.textDisabled
                font.family: Theme.fontMono
                font.pixelSize: Theme.metrics.fontSizeBody
                background: Rectangle {
                    color: Theme.colors.inputFill
                    border.color: input.activeFocus
                                  ? Theme.colors.inputFocusedBorder
                                  : Theme.colors.inputBorder
                    border.width: 1
                    radius: 0
                }

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
