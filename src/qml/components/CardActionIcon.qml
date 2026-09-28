import QtQuick

// One flat header action icon: a monospace glyph from the bundled Sarasa font
// (the project has no icon font/SVG pack) with a hover tint and a click signal.
// Mirrors the ChatTabBar close-button pattern so all card actions look alike.
Item {
    id: root

    property string glyph: ""
    property color iconColor: Theme.colors.textSecondary
    property color hoverColor: Theme.colors.textPrimary

    signal clicked()

    implicitWidth: 16
    implicitHeight: 16
    opacity: enabled ? 1.0 : 0.4

    Text {
        anchors.centerIn: parent
        text: root.glyph
        color: mouseArea.containsMouse ? root.hoverColor : root.iconColor
        font.family: Theme.fontMono
        font.pointSize: Theme.metrics.fontSizeBase
    }

    MouseArea {
        id: mouseArea
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
