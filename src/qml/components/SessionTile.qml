import QtQuick
import QtQuick.Layouts

Rectangle {
    id: tile

    property string sessionId: ""
    property string title: ""
    property string status: ""
    property bool isActive: false
    property bool isBlinking: false
    property int messageCount: 0
    property color dotColor: Theme.colors.sessionEmpty

    // True while this tile is the active drag source.
    readonly property bool dragging: dragArea.drag.active

    signal clicked()
    signal deleteRequested()
    signal dragBegan()
    signal dragFinished()

    implicitHeight: 48
    color: tile.isActive ? Theme.colors.sessionSelectedBg : Theme.colors.surfaceBg
    border.color: Theme.colors.borderLight
    border.width: 1
    radius: 0

    // The whole tile is the drag handle. The RowLayout below is stacked on top
    // so the delete button keeps receiving its own clicks; drags started on the
    // delete button are intentionally not draggable.
    MouseArea {
        id: dragArea
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton
        drag.target: dragFeedback
        drag.threshold: 6
        onClicked: {
            if (!tile.dragging)
                tile.clicked()
        }
    }

    // Drag feedback proxy matching the Flet edition's ``content_feedback``.
    // It follows the cursor via ``drag.target``; the Drag attached properties
    // live on this proxy (the real drag target) while ``Drag.source`` points
    // back at the tile so drop areas can read ``sessionId``.
    Rectangle {
        id: dragFeedback
        x: 0
        y: 0
        width: tile.width
        height: tile.height
        z: 1000
        visible: tile.dragging
        opacity: 0.9
        color: Theme.colors.dragFeedbackBg
        border.color: Theme.colors.dragFeedbackBorder
        border.width: 1
        radius: Theme.metrics.dropZoneRadius

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 6
            anchors.rightMargin: 6
            spacing: 4

            Text {
                text: "\u283f"
                color: Theme.colors.dragIcon
                font.family: Theme.fontMono
                font.pixelSize: Theme.metrics.fontSizeBody
            }

            Text {
                Layout.fillWidth: true
                text: tile.title
                color: Theme.colors.textPrimary
                font.family: Theme.fontMono
                font.pixelSize: Theme.metrics.fontSizeBody
                elide: Text.ElideRight
                maximumLineCount: 1
            }
        }

        Drag.active: dragArea.drag.active
        Drag.source: tile
        Drag.keys: ["session"]
        Drag.hotSpot.x: 8
        Drag.hotSpot.y: 8
        Drag.mimeData: ({ "text/plain": tile.sessionId })
        Drag.dragType: Drag.Internal
        Drag.supportedActions: Qt.MoveAction
        Drag.proposedAction: Qt.MoveAction
        Drag.onDragStarted: tile.dragBegan()
        Drag.onDragFinished: tile.dragFinished()
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 8
        anchors.rightMargin: 6
        spacing: 6

        Rectangle {
            id: statusDot
            Layout.alignment: Qt.AlignVCenter
            width: 10
            height: 10
            radius: Theme.metrics.statusDotRadius
            color: tile.dotColor

            SequentialAnimation on opacity {
                running: tile.isBlinking
                loops: Animation.Infinite

                NumberAnimation { to: 0.2; duration: 300; easing.type: Easing.InOutQuad }
                NumberAnimation { to: 1.0; duration: 300; easing.type: Easing.InOutQuad }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignVCenter
            spacing: 0

            Text {
                Layout.fillWidth: true
                text: tile.title
                color: Theme.colors.textPrimary
                font.family: Theme.fontMono
                font.pixelSize: Theme.metrics.fontSizeBody
                elide: Text.ElideRight
                maximumLineCount: 1
            }

            Text {
                Layout.fillWidth: true
                text: tile.messageCount + " msg"
                color: Theme.colors.textSecondary
                font.family: Theme.fontMono
                font.pixelSize: Theme.metrics.fontSizeLabelSmall
                elide: Text.ElideRight
                maximumLineCount: 1
            }
        }

        Rectangle {
            id: deleteButton
            Layout.alignment: Qt.AlignVCenter
            implicitWidth: 20
            implicitHeight: 20
            color: deleteArea.containsMouse ? Theme.colors.hoverBg : "transparent"
            border.color: Theme.colors.borderDefault
            border.width: 1
            radius: 0

            Text {
                anchors.centerIn: parent
                text: "\u00d7"
                color: Theme.colors.textSecondary
                font.family: Theme.fontMono
                font.pixelSize: Theme.metrics.fontSizeBody
            }

            MouseArea {
                id: deleteArea
                anchors.fill: parent
                hoverEnabled: true
                onClicked: tile.deleteRequested()
            }
        }
    }
}
