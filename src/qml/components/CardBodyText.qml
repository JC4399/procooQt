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

    // Emitted when the caret moves while this editor is focused; the hosting
    // card re-emits it so the panel can scroll the caret on screen.
    signal caretMoved(real caretY, real caretHeight)

    function focusEditor() {
        if (root.visible)
            root.forceActiveFocus()
    }

    Layout.fillWidth: true
    Layout.preferredHeight: contentHeight
    readOnly: true
    textFormat: TextEdit.RichText
    text: root.bodyHtml
    color: root.textColor
    font.family: Theme.fontMono
    font.pointSize: Theme.metrics.fontSizeMarkdown
    wrapMode: TextEdit.Wrap
    selectByMouse: true
    // Read-only editors disable keyboard selection by default; force it on so
    // shift+arrow / ctrl+arrow / home/end select.
    selectByKeyboard: true
    activeFocusOnTab: root.caretActive
    persistentSelection: true
    selectionColor: Theme.colors.selectionBg
    selectedTextColor: Theme.colors.selectionFg
    // Set imperatively (not a binding) so Qt's blink timer can toggle
    // cursorVisible without clobbering the focus link.
    onActiveFocusChanged: root.cursorVisible = root.activeFocus
    // Read-only editors do not paint the built-in cursor, so a custom delegate
    // draws (and blinks) the caret instead.
    cursorDelegate: Component {
        Rectangle {
            objectName: "caretCursor"
            width: 2
            height: Math.max(1, root.cursorRectangle.height)
            color: Theme.colors.textPrimary

            SequentialAnimation on opacity {
                loops: Animation.Infinite
                running: root.activeFocus
                NumberAnimation { from: 1; to: 1; duration: 500 }
                NumberAnimation { from: 1; to: 0; duration: 0 }
                NumberAnimation { from: 0; to: 0; duration: 500 }
                NumberAnimation { from: 0; to: 1; duration: 0 }
            }
        }
    }
    onCursorRectangleChanged: {
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
