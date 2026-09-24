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
    // Vertical breathing room applied by the ChatPanel delegate outside the card
    // border; UserCard overrides both to 24 px.
    property int padTop: 8
    property int padBottom: 8
    // True once a body exists. Pending thinking/response cards stream their body
    // in; the spinner is shown only while pending with no body yet.
    readonly property bool hasBody: card.bodyHtml !== ""

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

    implicitHeight: layout.implicitHeight
    color: Theme.colors.bubbleAssistant
    border.color: card.borderAllSides ? card.accentColor : "transparent"
    border.width: card.borderAllSides ? card.accentWidth : 0
    radius: Theme.metrics.cardRadius

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

            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    bodyHost.animateBody = true
                    card.bodyCollapsed = !card.bodyCollapsed
                }
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

                TextEdit {
                    Layout.fillWidth: true
                    Layout.preferredHeight: contentHeight
                    // Collapsed bodies are not made visible, so Qt skips laying
                    // out and rendering their rich text. Older cards are built
                    // collapsed; clicking the header expands them.
                    visible: card.hasBody && !card.bodyCollapsed
                    readOnly: true
                    textFormat: TextEdit.RichText
                    text: card.bodyHtml
                    color: (card.kind === "thinking" || card.kind === "response")
                           ? Theme.colors.mdText
                           : Theme.colors.textPrimary
                    font.family: Theme.fontMono
                    font.pointSize: Theme.metrics.fontSizeMarkdown
                    wrapMode: TextEdit.Wrap
                    selectByMouse: true
                    onLinkActivated: function (link) {
                        Qt.openUrlExternally(link)
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
