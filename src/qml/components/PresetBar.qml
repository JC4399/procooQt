import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Preset controls: load an existing preset, save the current sidebar
// selections under a typed name, or delete the selected preset.
Rectangle {
    id: bar

    property var presetNames: []

    signal loadRequested(string name)
    signal saveRequested(string name)
    signal deleteRequested(string name)

    implicitHeight: content.implicitHeight + 12
    color: Theme.colors.surfaceBg
    border.color: Theme.colors.borderDefault
    border.width: 1
    radius: 0

    component FlatButton: Button {
        id: control

        property color baseColor: Theme.colors.surfaceBg
        property color labelColor: Theme.colors.textPrimary

        implicitHeight: 26
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
        anchors.leftMargin: 8
        anchors.rightMargin: 8
        spacing: 6

        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            ComboBox {
                id: presetCombo
                Layout.fillWidth: true
                implicitHeight: 26
                font.family: Theme.fontMono
                font.pointSize: Theme.metrics.fontSizeBase
                model: bar.presetNames

                background: Rectangle {
                    color: Theme.colors.inputFill
                    border.color: presetCombo.activeFocus
                                  ? Theme.colors.inputFocusedBorder
                                  : Theme.colors.inputBorder
                    border.width: 1
                    radius: 0
                }

                contentItem: Text {
                    leftPadding: 6
                    text: presetCombo.displayText
                    color: Theme.colors.inputText
                    font: presetCombo.font
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }

                indicator: Text {
                    x: presetCombo.width - width - 6
                    y: presetCombo.topPadding + (presetCombo.availableHeight - height) / 2
                    text: "\u25be"
                    color: Theme.colors.textSecondary
                    font.family: Theme.fontMono
                    font.pointSize: Theme.metrics.fontSizeBase
                }

                delegate: ItemDelegate {
                    width: presetCombo.width
                    height: 24
                    highlighted: presetCombo.highlightedIndex === index
                    background: Rectangle {
                        color: highlighted ? Theme.colors.hoverBg : Theme.colors.surfaceBg
                        border.color: Theme.colors.borderLight
                        border.width: 1
                        radius: 0
                    }
                    contentItem: Text {
                        text: modelData
                        color: Theme.colors.textPrimary
                        font.family: Theme.fontMono
                        font.pointSize: Theme.metrics.fontSizeBase
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                    }
                }
            }

            FlatButton {
                text: qsTr("Load")
                baseColor: Theme.colors.buttonPrimaryBg
                labelColor: Theme.colors.buttonPrimaryFg
                onClicked: bar.loadRequested(presetCombo.currentIndex >= 0
                                              ? presetCombo.currentText : "")
            }

            FlatButton {
                text: qsTr("Delete")
                onClicked: bar.deleteRequested(presetCombo.currentIndex >= 0
                                               ? presetCombo.currentText : "")
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            TextField {
                id: nameField
                Layout.fillWidth: true
                implicitHeight: 26
                placeholderText: qsTr("Save Preset")
                text: skill.presetName
                color: Theme.colors.inputText
                placeholderTextColor: Theme.colors.textDisabled
                font.family: Theme.fontMono
                font.pointSize: Theme.metrics.fontSizeBase
                background: Rectangle {
                    color: Theme.colors.inputFill
                    border.color: nameField.activeFocus
                                  ? Theme.colors.inputFocusedBorder
                                  : Theme.colors.inputBorder
                    border.width: 1
                    radius: 0
                }
            }

            FlatButton {
                text: qsTr("Save")
                onClicked: bar.saveRequested(nameField.text)
            }
        }
    }
}
