import QtQuick

// Shared flat toggle indicator: a 12x12 square with a 2px corner radius, an
// accent border when checked, and a 6x6 accent dot inside. Instantiated by
// FlatCheckBox, FlatRadio and AutoScrollToggle so every toggle looks identical.
Rectangle {
    id: indicator

    property bool checked: false
    property color accent: Theme.colors.accentCyan

    width: Theme.metrics.controlIndicatorSize
    height: Theme.metrics.controlIndicatorSize
    color: "transparent"
    border.color: indicator.checked ? indicator.accent : Theme.colors.borderStrong
    border.width: 1
    radius: Theme.metrics.controlIndicatorRadius

    Rectangle {
        anchors.centerIn: parent
        width: Theme.metrics.controlDotSize
        height: Theme.metrics.controlDotSize
        visible: indicator.checked
        color: indicator.accent
        radius: 1
    }
}
