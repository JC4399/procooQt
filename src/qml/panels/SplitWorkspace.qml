import QtQuick
import QtQuick.Layouts
import QtQuick.Window

// VS Code-like split workspace: one to four equal-width chat panels side by side.
// All panels belong to the active session; each has its own tab bar. Panel widths
// are equal and not user-adjustable. Dragging a chat tab shows a ghost and, on
// release, splits the hovered panel or moves the chat to it.
Item {
    id: workspace

    signal openEditorRequested()

    property string dragChatId: ""
    property string dragTitle: ""
    property bool dragging: false
    property real dragX: -1000
    property real dragY: -1000
    property int hoverIndex: -1
    property string hoverSide: ""

    RowLayout {
        id: workspaceRow
        anchors.fill: parent
        spacing: 0

        Repeater {
            model: session.panelCount

            delegate: ChatPanel {
                Layout.fillWidth: true
                Layout.fillHeight: true
                panelIndex: index
                panelModel: session.panelAt(index)
                dropHint: workspace.hoverIndex === index ? workspace.hoverSide : ""
                onOpenEditorRequested: workspace.openEditorRequested()
                onDragStarted: function (chatId, title, sx, sy) {
                    workspace.beginDrag(chatId, title, sx, sy)
                }
                onDragMoved: function (sx, sy) { workspace.updateDrag(sx, sy) }
                onDragEnded: function (chatId, sx, sy) { workspace.finishDrag(chatId, sx, sy) }
                onDragCanceled: workspace.cancelDrag()
            }
        }
    }

    // Ghost box following the cursor during a drag.
    Rectangle {
        id: ghost
        width: 160
        height: 24
        x: workspace.dragX - width / 2
        y: workspace.dragY - height / 2
        z: 1000
        visible: workspace.dragging
        opacity: 0.9
        color: Theme.colors.dragFeedbackBg
        border.color: Theme.colors.dragFeedbackBorder
        border.width: 1
        radius: 0

        Text {
            anchors.centerIn: parent
            width: Math.max(0, parent.width - 12)
            text: workspace.dragTitle
            color: Theme.colors.textPrimary
            font.family: Theme.fontMono
            font.pointSize: Theme.metrics.fontSizeBase
            elide: Text.ElideRight
            horizontalAlignment: Text.AlignHCenter
        }
    }

    // ------------------------------------------------------------------
    //  Drag handling (window/scene coords in, workspace-local stored)
    // ------------------------------------------------------------------

    function beginDrag(chatId, title, sx, sy) {
        workspace.dragChatId = chatId
        workspace.dragTitle = title
        workspace.dragging = true
        workspace.updateDrag(sx, sy)
    }

    function toLocal(sx, sy) {
        var root = Window.window ? Window.window.contentItem : null
        return workspace.mapFromItem(root, sx, sy)
    }

    function updateDrag(sx, sy) {
        var p = workspace.toLocal(sx, sy)
        workspace.dragX = p.x
        workspace.dragY = p.y
        var hit = workspace.panelAtPoint(p.x, p.y)
        workspace.hoverIndex = hit.index
        workspace.hoverSide = hit.side
    }

    function finishDrag(chatId, sx, sy) {
        workspace.dragging = false
        var p = workspace.toLocal(sx, sy)
        var hit = workspace.panelAtPoint(p.x, p.y)
        workspace.hoverIndex = -1
        workspace.hoverSide = ""
        if (hit.index < 0)
            return
        if (hit.side === "move")
            session._handle_move_chat(chatId, hit.index)
        else if (hit.side === "left" || hit.side === "right")
            session._handle_split(chatId, hit.index, hit.side)
    }

    function cancelDrag() {
        workspace.dragging = false
        workspace.hoverIndex = -1
        workspace.hoverSide = ""
    }

    // Return {index, side} for the panel under a workspace-local point.
    function panelAtPoint(x, y) {
        var kids = workspaceRow.children
        for (var i = 0; i < kids.length; i++) {
            var child = kids[i]
            if (child.panelIndex === undefined)
                continue
            var lp = child.mapFromItem(workspace, x, y)
            if (lp.x < 0 || lp.y < 0 || lp.x > child.width || lp.y > child.height)
                continue
            if (lp.y <= child.tabBarHeight)
                return { "index": child.panelIndex, "side": "move" }
            // At the four-panel limit no new panel can be created, so suppress
            // the split hint; only grouping onto a tab bar is allowed.
            if (session.panelCount >= 4)
                return { "index": -1, "side": "" }
            return {
                "index": child.panelIndex,
                "side": lp.x < child.width / 2 ? "left" : "right"
            }
        }
        return { "index": -1, "side": "" }
    }
}
