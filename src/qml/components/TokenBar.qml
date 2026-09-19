import QtQuick
import QtQuick.Layouts

// Live token accounting for the active session, bound to the chat controller's
// inputTokens / outputTokens properties.
Rectangle {
    id: bar

    visible: chat.inputTokens > 0 || chat.outputTokens > 0
    implicitHeight: 24
    color: Theme.colors.surfaceBg
    border.color: Theme.colors.borderDefault
    border.width: 1
    radius: 0

    RowLayout {
        anchors.left: parent.left
        anchors.leftMargin: 8
        anchors.verticalCenter: parent.verticalCenter
        spacing: 2

        Text {
            text: "ctx: " + chat.inputTokens
            color: Theme.colors.textSecondary
            font.family: Theme.fontMono
            font.pointSize: Theme.metrics.fontSizeBase
        }

        Text {
            text: " + "
            color: Theme.colors.textSecondary
            font.family: Theme.fontMono
            font.pointSize: Theme.metrics.fontSizeBase
        }

        Text {
            text: "out: " + chat.outputTokens
            color: Theme.colors.textSecondary
            font.family: Theme.fontMono
            font.pointSize: Theme.metrics.fontSizeBase
        }

        Text {
            text: " = "
            color: Theme.colors.textSecondary
            font.family: Theme.fontMono
            font.pointSize: Theme.metrics.fontSizeBase
        }

        Text {
            text: "total: " + (chat.inputTokens + chat.outputTokens)
            color: Theme.colors.accentAmber
            font.family: Theme.fontMono
            font.pointSize: Theme.metrics.fontSizeBase
            font.bold: true
        }
    }
}
