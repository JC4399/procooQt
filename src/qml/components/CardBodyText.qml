import QtQuick
import QtQuick.Layouts

// One rich-text segment of a chat card body. A card stacks two instances: a
// frozen committed prefix (stable text) and a live streaming tail (grows every
// tick). Keeping the prefix in its own editor lets Qt cache its rich-text
// layout, so only the tail re-lays out on each stream tick instead of the whole
// accumulated document. View-only: text comes in via ``bodyHtml``.
TextEdit {
    id: root

    property string bodyHtml: ""
    property color textColor: Theme.colors.textPrimary
    // Flickable whose contentItem the caret scrolls to stay visible; null when
    // the card is unhosted.
    property var scrollTarget: null
    // False for the frozen prefix when a live tail follows, so only one editor
    // takes keyboard focus / tab.
    property bool caretActive: true
    // False only while the chat is streaming and the hosting panel's auto-scroll
    // is active, so the caret can never compete with the view being pinned to
    // the newest card. When idle it stays enabled even with auto-scroll on.
    property bool caretEnabled: true

    // Emitted when the caret moves while this editor is focused; the hosting
    // card re-emits it so the panel can scroll the caret on screen.
    signal caretMoved(real caretY, real caretHeight)

    function focusEditor() {
        if (root.visible && root.caretEnabled)
            root.forceActiveFocus()
    }

    Layout.fillWidth: true
    Layout.preferredHeight: contentHeight
    readOnly: true
    textFormat: TextEdit.RichText
    // Only materialize rich text while the body is actually shown. Collapsed
    // cards and hidden transcripts then hold no QTextDocument content.
    text: root.visible ? root.bodyHtml : ""
    color: root.textColor
    font.family: Theme.fontMono
    font.pointSize: Theme.metrics.fontSizeMarkdown
    wrapMode: TextEdit.Wrap
    selectByMouse: root.caretEnabled
    // Read-only editors disable keyboard selection by default; force it on so
    // shift+arrow / ctrl+arrow / home/end select.
    selectByKeyboard: true
    activeFocusOnPress: root.caretEnabled
    activeFocusOnTab: root.caretActive && root.caretEnabled
    persistentSelection: true
    selectionColor: Theme.colors.selectionBg
    selectedTextColor: Theme.colors.selectionFg
    // Show the delegate only while focused. Set imperatively rather than bound
    // so nothing clobbers the focus link.
    onActiveFocusChanged: root.cursorVisible = root.activeFocus
    onCaretEnabledChanged: {
        if (!root.caretEnabled && root.activeFocus)
            root.focus = false
    }
    // Read-only editors do not paint the built-in cursor, so a custom delegate
    // draws the caret. Qt does not blink it for a read-only editor, so a Timer
    // toggles the delegate's opacity. Cursor moves restart the blink in the
    // visible phase, so the caret always shows when it moves.
    property bool caretBlinkOn: true

    Timer {
        id: caretBlinkTimer
        interval: 500
        repeat: true
        running: root.activeFocus
        onTriggered: root.caretBlinkOn = !root.caretBlinkOn
        onRunningChanged: {
            if (running)
                root.caretBlinkOn = true
        }
    }

    cursorDelegate: Component {
        Rectangle {
            objectName: "caretCursor"
            width: 1
            height: Math.max(1, root.cursorRectangle.height)
            color: Theme.colors.textPrimary
            opacity: root.caretBlinkOn ? 1 : 0
        }
    }
    onCursorRectangleChanged: {
        // Show the caret solid on every move, then resume blinking.
        if (root.activeFocus) {
            root.caretBlinkOn = true
            caretBlinkTimer.restart()
        }
        if (!root.activeFocus || root.scrollTarget === null
                || root.scrollTarget.contentItem === null)
            return
        const p = root.mapToItem(
            root.scrollTarget.contentItem, cursorRectangle.x, cursorRectangle.y)
        root.caretMoved(p.y, cursorRectangle.height)
    }
    onLinkActivated: function (link) {
        Qt.openUrlExternally(link)
    }
}
