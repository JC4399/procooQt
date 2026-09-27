import QtQuick
import QtQuick.Controls

// Flat square action button shared by the automation and notification views.
// ``baseColor``/``labelColor`` default to the neutral surface style; pass the
// primary colours for a prominent action.
Button {
    id: control

    property color baseColor: Theme.colors.surfaceBg
    property color labelColor: Theme.colors.textPrimary

    implicitHeight: 26
    implicitWidth: Theme.metrics.buttonWidthMedium
    font.family: Theme.fontMono
    font.pointSize: Theme.metrics.fontSizeBase

    background: Rectangle {
        color: control.down ? Theme.colors.hoverBg : control.baseColor
        radius: Theme.metrics.buttonRadius
        border.color: Theme.colors.borderDefault
        border.width: 1
    }

    contentItem: Text {
        text: control.text
        color: control.enabled ? control.labelColor : Theme.colors.textDisabled
        font: control.font
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
}
