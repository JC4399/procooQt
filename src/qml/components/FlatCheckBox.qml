import QtQuick
import QtQuick.Controls

// Flat square check box sharing the common FlatIndicator look. Behaviour is
// inherited from CheckBox; only the visual indicator is customised.
CheckBox {
    id: control

    property color accent: Theme.colors.accentCyan

    implicitWidth: Theme.metrics.controlIndicatorSize
    implicitHeight: Theme.metrics.controlIndicatorSize

    indicator: FlatIndicator {
        anchors.centerIn: parent
        checked: control.checked
        accent: control.accent
    }

    contentItem: Item {}
}
