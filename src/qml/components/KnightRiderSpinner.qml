pragma ComponentBehavior: Bound

import QtQuick

// Bidirectional "Knight Rider" scanner: a row of block cells whose brightest
// cell sweeps right, holds, sweeps left, then holds, leaving a fading alpha
// trail behind it. View-only: the sweep is a precomputed frame index advanced
// by a Timer, and the per-cell glyph/colour is derived from the frame.
Item {
    id: root

    property color baseColor: Theme.colors.accentGreen
    property bool running: true
    property int cells: 8
    property int holdStart: 30
    property int holdEnd: 9
    property int trailSteps: 6
    property real inactiveAlpha: 0.2
    property real minAlpha: 0.3
    property int frameIntervalMs: 40
    property real bloomFactor: 1.15
    property real trailDecay: 0.65

    // Forward (cells) + hold at end + backward (cells - 1) + hold at start.
    readonly property int totalFrames: cells + holdEnd + (cells - 1) + holdStart
    readonly property bool animating: running

    property int frameIndex: 0
    property var trailPalette: []

    // ------------------------------------------------------------------
    //  Metrics
    // ------------------------------------------------------------------

    TextMetrics {
        id: glyphMetrics
        font.family: Theme.fontMono
        font.pointSize: Theme.metrics.fontSizeBase
        text: "\u25a0"
    }

    readonly property real cellWidth: Math.ceil(glyphMetrics.advanceWidth)
    readonly property real cellHeight: glyphMetrics.height

    implicitWidth: animating ? scannerRow.implicitWidth : staticLabel.implicitWidth
    implicitHeight: animating ? scannerRow.implicitHeight : staticLabel.implicitHeight

    // ------------------------------------------------------------------
    //  Frame maths
    // ------------------------------------------------------------------

    function rebuildPalette() {
        var r = baseColor.r
        var g = baseColor.g
        var b = baseColor.b
        var palette = []
        for (var i = 0; i < trailSteps; i++) {
            var alpha = 1.0
            var factor = 1.0
            if (i === 1) {
                alpha = 0.9
                factor = bloomFactor
            } else if (i > 1) {
                alpha = Math.pow(trailDecay, i - 1)
            }
            palette.push(Qt.rgba(Math.min(1.0, r * factor), Math.min(1.0, g * factor),
                                 Math.min(1.0, b * factor), alpha))
        }
        trailPalette = palette
    }

    function scannerState(frame) {
        var forwardFrames = cells
        var backwardFrames = cells - 1
        if (frame < forwardFrames) {
            return {
                pos: frame, holding: false, holdProgress: 0, holdTotal: 0,
                movementProgress: frame, movementTotal: forwardFrames, forward: true
            }
        }
        if (frame < forwardFrames + holdEnd) {
            return {
                pos: cells - 1, holding: true, holdProgress: frame - forwardFrames,
                holdTotal: holdEnd, movementProgress: 0, movementTotal: 0, forward: true
            }
        }
        if (frame < forwardFrames + holdEnd + backwardFrames) {
            var backwardIndex = frame - forwardFrames - holdEnd
            return {
                pos: cells - 2 - backwardIndex, holding: false, holdProgress: 0,
                holdTotal: 0, movementProgress: backwardIndex,
                movementTotal: backwardFrames, forward: false
            }
        }
        return {
            pos: 0, holding: true,
            holdProgress: frame - forwardFrames - holdEnd - backwardFrames,
            holdTotal: holdStart, movementProgress: 0, movementTotal: 0, forward: false
        }
    }

    function colorIndex(frame, cell) {
        var state = scannerState(frame)
        var distance = state.forward ? state.pos - cell : cell - state.pos
        if (state.holding)
            return distance + state.holdProgress
        if (distance > 0 && distance < trailSteps)
            return distance
        if (distance === 0)
            return 0
        return -1
    }

    function fadeFactor(state) {
        if (state.holding && state.holdTotal > 0) {
            var holdProgress = Math.min(state.holdProgress / state.holdTotal, 1)
            return Math.max(minAlpha, 1 - holdProgress * (1 - minAlpha))
        }
        if (!state.holding && state.movementTotal > 0) {
            var movementProgress = Math.min(
                state.movementProgress / Math.max(1, state.movementTotal - 1), 1)
            return minAlpha + movementProgress * (1 - minAlpha)
        }
        return 1.0
    }

    function isActive(cell) {
        var index = colorIndex(frameIndex, cell)
        return index >= 0 && index < trailSteps
    }

    function cellGlyph(cell) {
        return isActive(cell) ? "\u25a0" : "\u2b1d"
    }

    function cellColor(cell) {
        var index = colorIndex(frameIndex, cell)
        if (index >= 0 && index < trailPalette.length)
            return trailPalette[index]
        var state = scannerState(frameIndex)
        return Qt.rgba(baseColor.r, baseColor.g, baseColor.b,
                       inactiveAlpha * fadeFactor(state))
    }

    onBaseColorChanged: rebuildPalette()
    onTrailStepsChanged: rebuildPalette()
    Component.onCompleted: rebuildPalette()

    // ------------------------------------------------------------------
    //  Rendering
    // ------------------------------------------------------------------

    Timer {
        interval: root.frameIntervalMs
        repeat: true
        running: root.animating
        onTriggered: root.frameIndex = (root.frameIndex + 1) % root.totalFrames
    }

    Row {
        id: scannerRow
        visible: root.animating
        spacing: 1

        Repeater {
            model: root.cells

            delegate: Text {
                required property int index

                width: root.cellWidth
                height: root.cellHeight
                text: root.cellGlyph(index)
                color: root.cellColor(index)
                font.family: Theme.fontMono
                font.pointSize: Theme.metrics.fontSizeBase
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
        }
    }

    Text {
        id: staticLabel
        visible: !root.animating
        text: "[\u22ef]"
        color: root.baseColor
        font.family: Theme.fontMono
        font.pointSize: Theme.metrics.fontSizeBase
    }
}
