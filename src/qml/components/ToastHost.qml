import QtQuick
import QtQuick.Controls

Item {
    id: host

    property var notifier

    ListModel { id: toastModel }

    Column {
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 16
        spacing: 8

        Repeater {
            model: toastModel

            delegate: Rectangle {
                id: toast
                width: 360
                implicitHeight: messageText.implicitHeight + 20
                color: model.level === "error" ? Theme.colors.errorSnackbar
                       : (model.level === "info" ? Theme.colors.surfaceBg
                                                 : Theme.colors.warningSnackbar)
                border.color: model.level === "error" ? Theme.colors.accentRed
                              : (model.level === "info" ? Theme.colors.accentGreen
                                                        : Theme.colors.accentAmber)
                border.width: 1
                radius: Theme.metrics.toastRadius

                Text {
                    id: messageText
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.margins: 10
                    text: model.message
                    color: Theme.colors.toastText
                    font.family: Theme.fontMono
                    font.pixelSize: Theme.metrics.fontSizeBody
                    wrapMode: Text.WordWrap
                }

                Timer {
                    interval: 5000
                    running: true
                    onTriggered: toastModel.remove(index)
                }
            }
        }
    }

    Connections {
        target: host.notifier
        function onToast_requested(message, level) {
            toastModel.append({ "message": message, "level": level })
        }
    }
}
