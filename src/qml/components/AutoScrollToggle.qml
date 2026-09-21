import QtQuick

// Floating flat auto-scroll toggle. It fades in when auto-scroll becomes
// active (the chat is pinned to the newest card) and fades out when the user
// scrolls away; hovering a faded-out toggle reveals it so it stays clickable.
// View-only: the owner reacts to ``toggled``/``checked`` and drives the state
// through ``activateWithFade`` / ``deactivateWithFade``.
Item {
    id: control

    property bool checked: true
    property bool animating: false
    property real animOpacity: 0

    signal toggled()

    width: implicitWidth
    height: implicitHeight

    implicitWidth: row.implicitWidth + 16
    implicitHeight: 26

    // Symmetric 500 ms fades: in when auto-scroll activates, out when it stops.
    SequentialAnimation {
        id: fadeInAnim

        NumberAnimation {
            target: control
            property: "animOpacity"
            to: 1
            duration: 500
            easing.type: Easing.InOutQuad
        }
        ScriptAction {
            script: control.animating = false
        }
    }

    SequentialAnimation {
        id: fadeOutAnim

        NumberAnimation {
            target: control
            property: "animOpacity"
            to: 0
            duration: 500
            easing.type: Easing.InOutQuad
        }
        ScriptAction {
            script: control.animating = false
        }
    }

    function activateWithFade() {
        if (checked)
            return
        animOpacity = opacity
        checked = true
        animating = true
        fadeInAnim.restart()
    }

    function deactivateWithFade() {
        if (!checked)
            return
        // While hovered the toggle stays visible anyway, so skip the fade that
        // would otherwise pop back to full opacity when the hover takes over.
        if (mouseArea.containsMouse) {
            checked = false
            return
        }
        animOpacity = opacity
        checked = false
        animating = true
        fadeOutAnim.restart()
    }

    opacity: control.animating ? control.animOpacity
                               : (control.checked || mouseArea.containsMouse ? 1 : 0)

    Behavior on opacity {
        enabled: !control.animating
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

            FlatIndicator {
                anchors.verticalCenter: parent.verticalCenter
                checked: control.checked
                accent: Theme.colors.accentCyan
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
                if (control.checked)
                    control.deactivateWithFade()
                else
                    control.activateWithFade()
                control.toggled()
            }
        }
    }
}
