import QtQuick
import QtQuick.Controls.Material
import QtQuick.Layouts

ApplicationWindow {
    id: window
    width: 600
    height: 500
    visible: false
    title: "Vantage-X Control Hub"

    Material.theme: Material.Dark
    Material.accent: Material.Blue

    // Background color with rounded corners visual (simulated by inner rectangle if needed, but Window handles it on Wayland/KDE)
    color: Material.backgroundColor

    // Properties bound to backend
    property int chargeStart: 0
    property int chargeEnd: 0
    property int penPercentage: -1
    property string activeProfile: "balanced"

    Connections {
        target: dbusBackend
        function onChargeStartUpdated(threshold) { chargeStart = threshold }
        function onChargeEndUpdated(threshold) { chargeEnd = threshold }
        function onPenPercentageUpdated(percentage) { penPercentage = percentage }
        function onPowerProfileUpdated(profile) { activeProfile = profile }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 24

        // Header
        Label {
            text: "Vantage-X Hub"
            font.pixelSize: 24
            font.bold: true
            Layout.alignment: Qt.AlignHCenter
        }

        // Battery Thresholds
        GroupBox {
            title: "Battery Charge Thresholds"
            Layout.fillWidth: true

            ColumnLayout {
                anchors.fill: parent
                spacing: 16

                RowLayout {
                    Layout.fillWidth: true
                    Label { text: "Start Threshold: " + startSlider.value + "%"; Layout.preferredWidth: 150 }
                    Slider {
                        id: startSlider
                        from: 40; to: 95; stepSize: 1
                        value: chargeStart
                        Layout.fillWidth: true
                        onMoved: dbusBackend.setChargeStartThreshold(value)
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Label { text: "End Threshold: " + endSlider.value + "%"; Layout.preferredWidth: 150 }
                    Slider {
                        id: endSlider
                        from: 50; to: 100; stepSize: 1
                        value: chargeEnd
                        Layout.fillWidth: true
                        onMoved: dbusBackend.setChargeEndThreshold(value)
                    }
                }
            }
        }

        // Pen Status
        GroupBox {
            title: "ThinkPad Pen Status"
            Layout.fillWidth: true

            RowLayout {
                anchors.fill: parent
                Label {
                    text: penPercentage >= 0 ? "Battery: " + penPercentage + "%" : "Pen not detected"
                    font.pixelSize: 16
                }
            }
        }

        // Power Profiles
        GroupBox {
            title: "Power Profile"
            Layout.fillWidth: true

            RowLayout {
                anchors.fill: parent
                spacing: 16

                Button {
                    text: "Power Saver"
                    highlighted: activeProfile === "power-saver"
                    onClicked: dbusBackend.setPowerProfile("power-saver")
                    Layout.fillWidth: true
                    Layout.minimumHeight: 44
                }
                Button {
                    text: "Balanced"
                    highlighted: activeProfile === "balanced"
                    onClicked: dbusBackend.setPowerProfile("balanced")
                    Layout.fillWidth: true
                    Layout.minimumHeight: 44
                }
                Button {
                    text: "Performance"
                    highlighted: activeProfile === "performance"
                    onClicked: dbusBackend.setPowerProfile("performance")
                    Layout.fillWidth: true
                    Layout.minimumHeight: 44
                }
            }
        }

        // Miracast Stub
        GroupBox {
            title: "Miracast (Coming Soon)"
            Layout.fillWidth: true
            opacity: 0.5

            RowLayout {
                anchors.fill: parent
                Button {
                    text: "Scan for Displays"
                    enabled: false
                    Layout.fillWidth: true
                    Layout.minimumHeight: 44
                }
            }
        }

        Item { Layout.fillHeight: true } // Spacer
    }
}
