import QtQuick
import QtQuick.Layouts

// Combined active-config + token bar shown above the text input for one chat
// panel: four colored count squares (primary / allow / ask / block) at the left
// and the live total token count at the right.
Rectangle {
    id: bar

    property int primaryCount: 0
    property int allowCount: 0
    property int askCount: 0
    property int blockCount: 0
    property int inputTokens: 0
    property int outputTokens: 0
    property string modelName: ""

    implicitHeight: 26
    color: Theme.colors.surfaceBg
    border.color: Theme.colors.borderDefault
    border.width: 1
    radius: 0

    component CountSquare: Text {
        id: square

        property int count: 0
        property color squareColor: Theme.colors.textSecondary

        text: square.count
        color: square.squareColor
        font.family: Theme.fontMono
        font.pointSize: Theme.metrics.fontSizeBase
        font.bold: true
        verticalAlignment: Text.AlignVCenter
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 6
        anchors.rightMargin: 8
        spacing: 10

        CountSquare {
            Layout.alignment: Qt.AlignVCenter
            count: bar.primaryCount
            squareColor: Theme.colors.chipPrimaryFgMuted
        }

        CountSquare {
            Layout.alignment: Qt.AlignVCenter
            count: bar.allowCount
            squareColor: Theme.colors.chipAllowFgMuted
        }

        CountSquare {
            Layout.alignment: Qt.AlignVCenter
            count: bar.askCount
            squareColor: Theme.colors.chipAskFgMuted
        }

        CountSquare {
            Layout.alignment: Qt.AlignVCenter
            count: bar.blockCount
            squareColor: Theme.colors.chipBlockFgMuted
        }

        Text {
            Layout.alignment: Qt.AlignVCenter
            Layout.leftMargin: 4
            text: bar.modelName
            color: Theme.colors.textSecondary
            font.family: Theme.fontMono
            font.pointSize: Theme.metrics.fontSizeBase
            elide: Text.ElideRight
        }

        Item { Layout.fillWidth: true }

        Text {
            Layout.alignment: Qt.AlignVCenter
            text: (bar.inputTokens + bar.outputTokens) + " token"
            color: Theme.colors.textSecondary
            font.family: Theme.fontMono
            font.pointSize: Theme.metrics.fontSizeBase
        }
    }
}
