import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Active skills & tools bar shown above the chat list (mirrors the Flet edition's
// config tile). Collapsible header plus chips from ``skill.configChips``.
Rectangle {
    id: bar

    property bool expanded: true

    implicitHeight: content.implicitHeight
    color: Theme.colors.surfaceBg
    border.color: Theme.colors.borderDefault
    border.width: 1
    radius: 0

    Column {
        id: content
        width: bar.width

        Rectangle {
            id: headerRow
            width: parent.width
            height: 26
            color: Theme.colors.elevatedBg
            border.color: Theme.colors.borderDefault
            border.width: 1
            radius: 0

            MouseArea {
                anchors.fill: parent
                onClicked: bar.expanded = !bar.expanded
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 6
                anchors.rightMargin: 6
                spacing: 6

                Text {
                    text: bar.expanded ? "\u25bc" : "\u25b6"
                    color: Theme.colors.textSecondary
                    font.family: Theme.fontMono
                    font.pointSize: Theme.metrics.fontSizeBase
                }

                Text {
                    Layout.fillWidth: true
                    text: qsTr("Active Skills & Tools")
                    color: Theme.colors.textSecondary
                    font.family: Theme.fontMono
                    font.pointSize: Theme.metrics.fontSizeBase
                    elide: Text.ElideRight
                }
            }
        }

        Flow {
            id: chipFlow
            width: parent.width
            visible: bar.expanded
            spacing: 4
            padding: 6

            Text {
                visible: skill.configChips.length === 0
                text: qsTr("No skills or tools configured for this session.")
                color: Theme.colors.textDisabled
                font.family: Theme.fontMono
                font.pointSize: Theme.metrics.fontSizeBase
                font.italic: true
            }

            Repeater {
                model: skill.configChips

                delegate: Rectangle {
                    color: modelData.bg
                    border.color: Theme.colors.borderDefault
                    border.width: 1
                    radius: 0
                    implicitWidth: chipText.implicitWidth + 10
                    implicitHeight: chipText.implicitHeight + 4

                    Text {
                        id: chipText
                        anchors.centerIn: parent
                        text: modelData.label
                        color: modelData.fg
                        font.family: Theme.fontMono
                        font.pointSize: Theme.metrics.fontSizeBase
                    }
                }
            }
        }
    }
}
