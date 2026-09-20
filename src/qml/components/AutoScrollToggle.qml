import QtQuick

// Floating flat toggle that reveals itself on hover when unchecked and stays
// visible while checked. View-only: the owner reacts to ``toggled``/``checked``.
Item {
    id: control

    property bool checked: false
    property bool blinking: false
    property real blinkOpacity: 0

    signal toggled()

    width: implicitWidth
    height: implicitHeight

    implicitWidth: row.implicitWidth + 16
    implicitHeight: 26

    // Blink once (visible → hidden → visible) then fade out to hidden. Used to
    // signal that auto-scroll was switched off because the user scrolled away.
    SequentialAnimation {
        id: blinkAnim

        NumberAnimation {
            target: control
            property: "blinkOpacity"
            from: 1
            to: 0
            duration: 500
        }
        NumberAnimation {
            target: control
            property: "blinkOpacity"
            from: 0
            to: 1
            duration: 500
        }
        NumberAnimation {
            id: fadeOut
            target: control
            property: "blinkOpacity"
            from: 1
            to: 0
            duration: 500
            easing.type: Easing.InOutQuad
        }
        ScriptAction {
            script: control.blinking = false
        }
    }

    function deactivateWithBlink() {
        if (!checked)
            return
        checked = false
        blinking = true
        blinkAnim.restart()
    }

    opacity: control.blinking ? control.blinkOpacity
                              : (control.checked || mouseArea.containsMouse ? 1 : 0)

    Behavior on opacity {
        enabled: !control.blinking
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
