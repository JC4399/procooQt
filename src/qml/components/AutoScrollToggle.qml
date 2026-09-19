import QtQuick

// Floating flat toggle that reveals itself on hover when unchecked and stays
// visible while checked. View-only: the owner reacts to ``toggled``/``checked``.
Item {
    id: control

    property bool checked: false

    signal toggled()

    width: implicitWidth
    height: implicitHeight

    implicitWidth: row.implicitWidth + 16
    implicitHeight: 26

    opacity: control.checked || mouseArea.containsMouse ? 1 : 0

    Behavior on opacity {
        NumberAnimation {
            duration: 120
        }
    }

    Rectangle {
        id: background
        anchors.fill: parent
        color: mouseArea.containsMouse ? Theme.colors.hoverBg : Theme.colors.surfaceBg
        border.color: control.checked ? Theme.colors.accentCyan : Theme.colors.borderDefault
        border.width: 1
        radius: 0

        Row {
            id: row
            anchors.centerIn: parent
            spacing: 6

            Rectangle {
                width: 10
                height: 10
                anchors.verticalCenter: parent.verticalCenter
                color: control.checked ? Theme.colors.accentCyan : "transparent"
                border.color: Theme.colors.textSecondary
                border.width: 1
                radius: 0
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: qsTr("Auto-scroll")
                color: control.checked ? Theme.colors.textPrimary : Theme.colors.textSecondary
                font.family: Theme.fontMono
                font.pointSize: Theme.metrics.fontSizeBase
            }
        }

        MouseArea {
            id: mouseArea
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                control.checked = !control.checked
                control.toggled()
            }
        }
    }
}
