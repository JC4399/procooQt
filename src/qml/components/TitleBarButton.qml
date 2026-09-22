import QtQuick

// Reusable flat square window-control button for the frameless title bar.
// View-only: the owner connects ``clicked`` and supplies the glyph text and
// whether the button is destructive (``danger``, e.g. the close button).
Rectangle {
    id: control

    property string glyph: ""
    property bool danger: false

    signal clicked()

    implicitWidth: Theme.metrics.titleBarButtonWidth
    implicitHeight: Theme.metrics.titleBarHeight
    color: mouseArea.containsMouse
           ? (control.danger ? Theme.colors.buttonPrimaryBg : Theme.colors.hoverBg)
           : Theme.colors.surfaceBg
    radius: Theme.metrics.buttonRadius

    Text {
        anchors.centerIn: parent
        text: control.glyph
        color: mouseArea.containsMouse && control.danger
               ? Theme.colors.buttonPrimaryFg
               : Theme.colors.textSecondary
        font.family: Theme.fontMono
        font.pointSize: Theme.metrics.fontSizeBase
    }

    MouseArea {
        id: mouseArea
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: control.clicked()
    }
}
