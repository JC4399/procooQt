import QtQuick
import QtQuick.Window

// VS Code-like split workspace: one to four equal-width chat panels side by side.
// Panels occupy a fixed set of slots (SessionController.MAX_PANELS), so adding,
// removing, or moving a panel only changes each delegate's x and visibility —
// never the delegate itself. A panel keeps its ChatPanelModel as it moves, so
// untouched panels are never rebuilt. Dragging a chat tab shows a ghost and, on
// release, splits the hovered panel or moves the chat to it.
Item {
    id: workspace

    signal openEditorRequested()

    // Number of fixed panel slots; mirrors SessionController.MAX_PANELS.
    readonly property int slotCount: session.maxPanels

    property string dragChatId: ""
    property string dragTitle: ""
    property bool dragging: false
    property real dragX: -1000
    property real dragY: -1000
    property int hoverSlot: -1
    property string hoverSide: ""
    // Panel rectangles captured once at drag start; geometry is fixed mid-drag,
    // so hit-testing avoids a per-move mapFromItem over every panel.
    property var panelRects: []

    Item {
        id: panelsLayer
        anchors.fill: parent

        Repeater {
            model: workspace.slotCount

            delegate: ChatPanel {
                // Visual position of this fixed slot (-1 when the slot is unused).
                readonly property int visualIndex: session.panelOrder.indexOf(index)
                readonly property real panelWidth:
                    session.panelCount > 0 ? panelsLayer.width / session.panelCount : 0

                visible: visualIndex >= 0
                x: visualIndex * panelWidth
                width: panelWidth
                height: panelsLayer.height
                slot: index
                panelModel: session.panelAt(index)
                dropHint: workspace.hoverSlot === index ? workspace.hoverSide : ""
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
        // Rendered to its own texture so following the cursor composites a
        // cached layer instead of re-rasterizing the ghost every move.
        layer.enabled: true
        layer.smooth: false

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
        workspace.panelRects = workspace.capturePanelRects()
        workspace.updateDrag(sx, sy)
    }

    // Snapshot each visible panel's rect (workspace coords) for fast hit-testing.
    function capturePanelRects() {
        var rects = []
        var kids = panelsLayer.children
        for (var i = 0; i < kids.length; i++) {
            var child = kids[i]
            if (child.slot === undefined || !child.visible)
                continue
            var tl = child.mapToItem(workspace, 0, 0)
            rects.push({
                "slot": child.slot,
                "x": tl.x,
                "y": tl.y,
                "w": child.width,
                "h": child.height,
                "tabBarHeight": child.tabBarHeight
            })
        }
        return rects
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
        workspace.hoverSlot = hit.slot
        workspace.hoverSide = hit.side
    }

    function finishDrag(chatId, sx, sy) {
        workspace.dragging = false
        var p = workspace.toLocal(sx, sy)
        var hit = workspace.panelAtPoint(p.x, p.y)
        workspace.hoverSlot = -1
        workspace.hoverSide = ""
        if (hit.slot < 0)
            return
        if (hit.side === "move")
            session._handle_move_chat(chatId, hit.slot)
        else if (hit.side === "left" || hit.side === "right")
            session._handle_split(chatId, hit.slot, hit.side)
    }

    function cancelDrag() {
        workspace.dragging = false
        workspace.hoverSlot = -1
        workspace.hoverSide = ""
    }

    // Return {slot, side} for the panel under a workspace-local point.
    function panelAtPoint(x, y) {
        var rects = workspace.panelRects
        for (var i = 0; i < rects.length; i++) {
            var r = rects[i]
            if (x < r.x || y < r.y || x > r.x + r.w || y > r.y + r.h)
                continue
            if (y - r.y <= r.tabBarHeight)
                return { "slot": r.slot, "side": "move" }
            // At the four-panel limit no new panel can be created, so suppress
            // the split hint; only grouping onto a tab bar is allowed.
            if (session.panelCount >= session.maxPanels)
                return { "slot": -1, "side": "" }
            return {
                "slot": r.slot,
                "side": (x - r.x) < r.w / 2 ? "left" : "right"
            }
        }
        return { "slot": -1, "side": "" }
    }
}
