import QtQuick
import QtQuick.Layouts

import "../components"

// Shared chat-card anatomy: header row (icon + label + optional mode badge +
// subtitle + token text) with a bottom divider, and a collapsible body. Every
// card under src/qml/cards/ inherits from this so header styling never duplicates.
// Pending cards use the same header by setting ``isPending``.
Rectangle {
    id: card

    property string kind: ""
    property string title: ""
    property string subtitle: ""
    property string bodyHtml: ""
    // Live streaming tail, rendered in its own editor after ``bodyHtml``. Empty
    // for finalized cards (whose whole body is in ``bodyHtml``).
    property string bodyTailHtml: ""
    property string tokenText: ""
    property string mode: ""
    property bool isPending: false
    property bool bodyCollapsed: false
    property color accentColor: Theme.colors.borderDefault
    property color headerColor: Theme.colors.textSecondary
    property int accentWidth: 2
    property bool borderAllSides: true
    // When false the header row is hidden and the card renders body only
    // (used by the headerless waiting placeholder).
    property bool headerVisible: true
    property string iconGlyph: ""
    // Index of the source message in chat.messages, bound from the model. Drives
    // the delete/regenerate card actions; -1 means no message (derived cards).
    property int msgIndex: -1
    // False while the chat is generating, so the card actions are inert.
    property bool actionsEnabled: true
    // Flickable whose ``contentItem`` the card scrolls to keep the body caret
    // visible during keyboard navigation. Bound by the hosting panel; null when
    // the card is unhosted.
    property var scrollTarget: null
    // False while the hosting panel's auto-scroll is active. The caret is then
    // disabled so it cannot pull the viewport away from the newest card.
    property bool caretEnabled: true

    signal deleteRequested(int msgIndex)
    signal regenerateRequested(int msgIndex)
    // Emitted when the body caret moves while the editor is focused; the hosting
    // panel scrolls ``scrollTarget`` so the caret stays on screen.
    signal caretMoved(real caretY, real caretHeight)
    // Vertical breathing room applied by the ChatPanel delegate outside the card
    // border; UserCard overrides both to 24 px.
    property int padTop: 8
    property int padBottom: 8
    // True once a body exists. Pending thinking/response cards stream their body
    // in; the spinner is shown only while pending with no body yet.
    readonly property bool hasBody: card.bodyHtml !== "" || card.bodyTailHtml !== ""
    // Body text colour: markdown cards use the markdown text colour, all other
    // cards use the primary text colour.
    readonly property color bodyColor: (card.kind === "thinking" || card.kind === "response")
                                        ? Theme.colors.mdText
                                        : Theme.colors.textPrimary

    function modeBg(value) {
        if (value === "allow")
            return Theme.colors.toolModeAllowBg
        if (value === "block")
            return Theme.colors.toolModeBlockBg
        return Theme.colors.toolModeAskBg
    }

    function modeFg(value) {
        if (value === "allow")
            return Theme.colors.toolModeAllowFg
        if (value === "block")
            return Theme.colors.toolModeBlockFg
        return Theme.colors.toolModeAskFg
    }

    // Focus the body rich-text editor so it receives keyboard caret navigation.
    // Collapsed or bodyless cards have no caret target. The live tail takes
    // focus when present, otherwise the frozen prefix.
    function focusBody() {
        if (!card.hasBody || card.bodyCollapsed || !card.caretEnabled)
            return
        if (bodyText.bodyHtml !== "")
            bodyText.focusEditor()
        else
            prefixText.focusEditor()
    }

    implicitHeight: layout.implicitHeight
    color: Theme.colors.bubbleAssistant
    border.color: card.borderAllSides ? card.accentColor : "transparent"
    border.width: card.borderAllSides ? card.accentWidth : 0
    radius: Theme.metrics.cardRadius

    // Declared first (lowest z) so it only receives clicks on empty card areas
    // the header row, action icons, and body editor do not consume. Clicking any
    // such area hands the caret to the body, making the whole card feel like a
    // selectable text surface.
    MouseArea {
        anchors.fill: parent
        onClicked: card.focusBody()
    }

    ColumnLayout {
        id: layout
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        spacing: 0

        // ----------------------------------------------------------
        //  Header row + divider
        // ----------------------------------------------------------
        Rectangle {
            id: header
            Layout.fillWidth: true
            visible: card.headerVisible
            implicitHeight: headerRow.implicitHeight + 8
            color: "transparent"

            // Declared before the row so the icons (declared later) sit on top
            // and consume their clicks; clicks on plain header text fall through.
            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    bodyHost.animateBody = true
                    card.bodyCollapsed = !card.bodyCollapsed
                    // Expanding a card hands the caret to its body so keyboard
                    // navigation starts immediately; collapsing just hides it.
                    if (!card.bodyCollapsed && card.hasBody)
                        Qt.callLater(card.focusBody)
                }
            }

            RowLayout {
                id: headerRow
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 6

                Text {
                    visible: card.iconGlyph !== ""
                    text: card.iconGlyph
                    color: card.headerColor
                    font.family: Theme.fontMono
                    font.pointSize: Theme.metrics.fontSizeBase
                }

                Text {
                    text: card.title
                    color: card.headerColor
                    font.family: Theme.fontMono
                    font.pointSize: Theme.metrics.fontSizeBase
                    font.bold: true
                }

                Rectangle {
                    visible: card.mode !== ""
                    implicitWidth: modeLabel.implicitWidth + 8
                    implicitHeight: modeLabel.implicitHeight + 4
                    color: card.modeBg(card.mode)
                    border.color: card.modeFg(card.mode)
                    border.width: 1
                    radius: Theme.metrics.modeBadgeRadius

                    Text {
                        id: modeLabel
                        anchors.centerIn: parent
                        text: card.mode
                        color: card.modeFg(card.mode)
                        font.family: Theme.fontMono
                        font.pointSize: Theme.metrics.fontSizeBase
                    }
                }

                Text {
                    visible: card.subtitle !== ""
                    text: card.subtitle
                    color: Theme.colors.textSecondary
                    font.family: Theme.fontMono
                    font.pointSize: Theme.metrics.fontSizeBase
                }

                Item { Layout.fillWidth: true }

                CardActionIcon {
                    glyph: "\uf021"
                    visible: card.kind === "user"
                    enabled: card.actionsEnabled
                    Layout.alignment: Qt.AlignVCenter
                    onClicked: card.regenerateRequested(card.msgIndex)
                }

                CardActionIcon {
                    glyph: "\uf1f8"
                    visible: card.msgIndex >= 0
                    enabled: card.actionsEnabled
                    Layout.alignment: Qt.AlignVCenter
                    onClicked: card.deleteRequested(card.msgIndex)
                }

                Text {
                    visible: card.tokenText !== ""
                    text: card.tokenText
                    color: Theme.colors.textSecondary
                    font.family: Theme.fontMono
                    font.pointSize: Theme.metrics.fontSizeBase
                }

                Text {
                    text: card.bodyCollapsed ? "\u25b8" : "\u25be"
                    color: Theme.colors.textSecondary
                    font.family: Theme.fontMono
                    font.pointSize: Theme.metrics.fontSizeBase
                }
            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 1
                color: Theme.colors.cardHeaderDivider
            }
        }

        // ----------------------------------------------------------
        //  Collapsible body (height animated on toggle)
        // ----------------------------------------------------------
        Item {
            id: bodyHost
            Layout.fillWidth: true
            Layout.preferredHeight: bodyHeight
            clip: true

            property real bodyHeight: card.bodyCollapsed ? 0 : (body.implicitHeight + 14)
            property bool animateBody: false

            Behavior on bodyHeight {
                enabled: bodyHost.animateBody
                NumberAnimation {
                    duration: 160
                    easing.type: Easing.InOutQuad
                }
            }

            ColumnLayout {
                id: body
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                anchors.topMargin: 6
                spacing: 0

                KnightRiderSpinner {
                    Layout.alignment: Qt.AlignHCenter
                    visible: card.isPending && !card.hasBody
                    running: visible
                    baseColor: card.accentColor
                }

                // Frozen committed prefix. Its text only changes when a new
                // Markdown block commits, so Qt keeps its rich-text layout
                // cached across stream ticks. Collapsed bodies are not made
                // visible, so Qt skips laying out their rich text entirely;
                // older cards are built collapsed and expand on header click.
                CardBodyText {
                    id: prefixText
                    bodyHtml: card.bodyHtml
                    textColor: card.bodyColor
                    scrollTarget: card.scrollTarget
                    caretEnabled: card.caretEnabled
                    // Only the tail takes focus when a live tail follows.
                    caretActive: bodyText.bodyHtml === ""
                    visible: card.bodyHtml !== "" && !card.bodyCollapsed
                    onCaretMoved: function (caretY, caretHeight) {
                        card.caretMoved(caretY, caretHeight)
                    }
                }

                // Live streaming tail. Re-laid out every tick, but now only the
                // uncommitted trailing block rather than the whole document.
                CardBodyText {
                    id: bodyText
                    bodyHtml: card.bodyTailHtml
                    textColor: card.bodyColor
                    scrollTarget: card.scrollTarget
                    caretEnabled: card.caretEnabled
                    visible: card.bodyTailHtml !== "" && !card.bodyCollapsed
                    onCaretMoved: function (caretY, caretHeight) {
                        card.caretMoved(caretY, caretHeight)
                    }
                }
            }
        }
    }

    // ----------------------------------------------------------
    //  Top/bottom-only borders (thinking / tool cards)
    // ----------------------------------------------------------
    Rectangle {
        visible: !card.borderAllSides
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: card.accentWidth
        color: card.accentColor
    }

    Rectangle {
        visible: !card.borderAllSides
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: card.accentWidth
        color: card.accentColor
    }
}
