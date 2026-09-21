import QtQuick
import QtQuick.Controls

// Flat square radio button sharing the common FlatIndicator look. Mutual
// exclusion still comes from a ButtonGroup on the consumer side.
RadioButton {
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
