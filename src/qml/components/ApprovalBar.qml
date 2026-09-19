import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Tool-approval bar. Hidden unless the chat controller reports a pending tool
// call; Approve/Deny release the blocked generation loop.
Rectangle {
    id: bar

    property bool resolving: false

    visible: chat.approvalVisible
    implicitHeight: visible ? content.implicitHeight + 16 : 0
    color: Theme.colors.approvalBg
    border.color: Theme.colors.approvalBorder
    border.width: 1
    radius: 0

    onVisibleChanged: {
        if (visible)
            bar.resolving = false
    }

    component FlatButton: Button {
        id: control

        property color baseColor: Theme.colors.surfaceBg
        property color labelColor: Theme.colors.textPrimary

        implicitHeight: 28
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

    ColumnLayout {
        id: content
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.margins: 8
        spacing: 6

        Text {
            Layout.fillWidth: true
            text: chat.approvalText
            color: Theme.colors.textPrimary
            font.family: Theme.fontMono
            font.pointSize: Theme.metrics.fontSizeBase
            wrapMode: Text.WordWrap
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            FlatButton {
                text: qsTr("Approve")
                baseColor: Theme.colors.buttonApproveBg
                labelColor: Theme.colors.buttonApproveFg
                enabled: !bar.resolving
                onClicked: {
                    bar.resolving = true
                    chat._handle_approve()
                }
            }

            FlatButton {
                text: qsTr("Deny")
                enabled: !bar.resolving
                onClicked: {
                    bar.resolving = true
                    chat._handle_deny(reasonField.text)
                }
            }

            TextField {
                id: reasonField
                Layout.fillWidth: true
                placeholderText: qsTr("Deny reason (Optional)")
                color: Theme.colors.inputText
                placeholderTextColor: Theme.colors.textDisabled
                font.family: Theme.fontMono
                font.pointSize: Theme.metrics.fontSizeBase
                background: Rectangle {
                    color: Theme.colors.inputFill
                    border.color: reasonField.activeFocus
                                  ? Theme.colors.inputFocusedBorder
                                  : Theme.colors.inputBorder
                    border.width: 1
                    radius: 0
                }
            }
        }
    }
}
