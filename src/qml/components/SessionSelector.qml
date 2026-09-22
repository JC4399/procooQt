import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Title-bar session selector: shows "Session: <name>" and drops down the session
// list. The last row is always a "+" that creates a new session; each session row
// has a cross that deletes it (after confirmation).
Rectangle {
    id: selector

    property string pendingDeleteSession: ""

    readonly property string label: qsTr("Session: ") + (session.activeSessionName || "Default")

    implicitWidth: 260
    implicitHeight: Theme.metrics.titleBarHeight
    color: Theme.colors.elevatedBg
    border.color: selectorPopup.visible ? Theme.colors.borderStrong : Theme.colors.borderDefault
    border.width: 1
    radius: 0

    component FlatButton: Button {
        id: control

        property color baseColor: Theme.colors.surfaceBg
        property color labelColor: Theme.colors.textPrimary

        implicitHeight: 26
        implicitWidth: 64
        font.family: Theme.fontMono
        font.pointSize: Theme.metrics.fontSizeBase

        background: Rectangle {
            color: control.down ? Theme.colors.hoverBg : control.baseColor
            radius: 0
            border.color: Theme.colors.borderDefault
            border.width: 1
        }

        contentItem: Text {
            text: control.text
            color: control.labelColor
            font: control.font
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
    }

    Text {
        anchors.centerIn: parent
        text: selector.label
        color: Theme.colors.textPrimary
        font.family: Theme.fontMono
        font.pointSize: Theme.metrics.fontSizeBase
        elide: Text.ElideRight
        width: Math.max(0, selector.width - 20)
        horizontalAlignment: Text.AlignHCenter
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton
        onClicked: selectorPopup.visible ? selectorPopup.close() : selectorPopup.open()
    }

    // ------------------------------------------------------------------
    //  Dropdown
    // ------------------------------------------------------------------

    Popup {
        id: selectorPopup
        y: selector.height
        x: 0
        width: selector.width
        padding: 0
        modal: false
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        background: Rectangle {
            color: Theme.colors.surfaceBg
            border.color: Theme.colors.borderDefault
            border.width: 1
            radius: 0
        }

        contentItem: ListView {
            id: sessionList
            clip: true
            implicitHeight: contentHeight
            model: session.sessionMenuModel

            delegate: Rectangle {
                width: sessionList.width
                height: 28
                color: model.is_active ? Theme.colors.chatSelectedBg
                                       : (rowArea.containsMouse ? Theme.colors.hoverBg
                                                                : Theme.colors.surfaceBg)
                border.color: Theme.colors.borderLight
                border.width: 1
                radius: 0

                MouseArea {
                    id: rowArea
                    anchors.fill: parent
                    hoverEnabled: true
                    enabled: !model.is_add
                    onClicked: {
                        session._handle_switch_session(model.name)
                        selectorPopup.close()
                    }
                }

                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    x: model.is_add ? 0 : 8
                    width: model.is_add ? parent.width : Math.max(0, parent.width - 40)
                    text: model.is_add ? qsTr("+") : model.name
                    color: model.is_add ? Theme.colors.accentCyan : Theme.colors.textPrimary
                    font.family: Theme.fontMono
                    font.pointSize: Theme.metrics.fontSizeBase
                    horizontalAlignment: model.is_add ? Text.AlignHCenter : Text.AlignLeft
                    elide: Text.ElideRight
                }

                Rectangle {
                    anchors.right: parent.right
                    anchors.rightMargin: 4
                    anchors.verticalCenter: parent.verticalCenter
                    width: 20
                    height: 20
                    visible: !model.is_add
                    color: deleteArea.containsMouse ? Theme.colors.hoverBg : "transparent"
                    border.color: Theme.colors.borderDefault
                    border.width: 1
                    radius: 0

                    Text {
                        anchors.centerIn: parent
                        text: "\u00d7"
                        color: Theme.colors.textSecondary
                        font.family: Theme.fontMono
                        font.pointSize: Theme.metrics.fontSizeBase
                    }

                    MouseArea {
                        id: deleteArea
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: {
                            selector.pendingDeleteSession = model.name
                            deleteSessionDialog.open()
                            selectorPopup.close()
                        }
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    visible: model.is_add
                    onClicked: {
                        newSessionDialog.open()
                        selectorPopup.close()
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------------
    //  New session dialog
    // ------------------------------------------------------------------

    Dialog {
        id: newSessionDialog
        anchors.centerIn: Overlay.overlay
        modal: true
        focus: true
        width: 320
        padding: 12
        background: Rectangle {
            color: Theme.colors.surfaceBg
            border.color: Theme.colors.borderDefault
            border.width: 1
            radius: 0
        }
        contentItem: ColumnLayout {
            spacing: 8
            Text {
                text: qsTr("Session name")
                color: Theme.colors.textPrimary
                font.family: Theme.fontMono
                font.pointSize: Theme.metrics.fontSizeBase
            }
            TextField {
                id: sessionNameField
                Layout.fillWidth: true
                placeholderText: qsTr("New session")
                color: Theme.colors.inputText
                placeholderTextColor: Theme.colors.textDisabled
                font.family: Theme.fontMono
                font.pointSize: Theme.metrics.fontSizeBase
                background: Rectangle {
                    color: Theme.colors.inputFill
                    border.color: sessionNameField.activeFocus
                                  ? Theme.colors.inputFocusedBorder
                                  : Theme.colors.inputBorder
                    border.width: 1
                    radius: 0
                }
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                Item { Layout.fillWidth: true }
                FlatButton {
                    text: qsTr("Cancel")
                    onClicked: newSessionDialog.close()
                }
                FlatButton {
                    text: qsTr("Create")
                    baseColor: Theme.colors.buttonPrimaryBg
                    labelColor: Theme.colors.buttonPrimaryFg
                    onClicked: {
                        session._handle_create_session(sessionNameField.text)
                        sessionNameField.text = ""
                        newSessionDialog.close()
                    }
                }
            }
        }
        onOpened: sessionNameField.forceActiveFocus()
    }

    // ------------------------------------------------------------------
    //  Delete session dialog
    // ------------------------------------------------------------------

    Dialog {
        id: deleteSessionDialog
        anchors.centerIn: Overlay.overlay
        modal: true
        focus: true
        width: 340
        padding: 12
        background: Rectangle {
            color: Theme.colors.surfaceBg
            border.color: Theme.colors.borderDefault
            border.width: 1
            radius: 0
        }
        contentItem: ColumnLayout {
            spacing: 10
            Text {
                Layout.fillWidth: true
                text: qsTr("Delete session \"") + selector.pendingDeleteSession
                      + qsTr("\" and all of its chats?")
                color: Theme.colors.textPrimary
                font.family: Theme.fontMono
                font.pointSize: Theme.metrics.fontSizeBase
                wrapMode: Text.WordWrap
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                Item { Layout.fillWidth: true }
                FlatButton {
                    text: qsTr("Cancel")
                    onClicked: deleteSessionDialog.close()
                }
                FlatButton {
                    text: qsTr("Delete")
                    baseColor: Theme.colors.buttonPrimaryBg
                    labelColor: Theme.colors.buttonPrimaryFg
                    onClicked: {
                        session._handle_delete_session(selector.pendingDeleteSession)
                        deleteSessionDialog.close()
                    }
                }
            }
        }
    }
}
