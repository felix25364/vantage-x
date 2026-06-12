#!/usr/bin/env bash

if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo ./setup.sh)"
    exit 1
fi

echo "Installing Arch Linux dependencies..."
# Install standard packages
pacman -S --needed --noconfirm python-pyqt6 qt6-declarative python-evdev python-pip qasync || true

# Check for dbus-next. It's often in AUR. If not present, install via pip.
if ! pacman -Qi python-dbus-next &>/dev/null; then
    echo "python-dbus-next not found in pacman, installing via pip..."
    pip install --break-system-packages dbus-next
fi

echo "Copying D-Bus configuration..."
cp dbus_specs/org.vantagex.daemon.conf /usr/share/dbus-1/system.d/

echo "Copying Daemon and GUI binaries..."
mkdir -p /usr/lib/vantage-x
cp daemon/main.py /usr/lib/vantage-x/vantagex-daemon.py
chmod +x /usr/lib/vantage-x/vantagex-daemon.py

cp gui/main.py /usr/lib/vantage-x/vantagex-gui.py
cp gui/Dashboard.qml /usr/lib/vantage-x/Dashboard.qml
chmod +x /usr/lib/vantage-x/vantagex-gui.py

echo "Creating GUI launcher in /usr/bin..."
cat << 'LAUNCHER' > /usr/bin/vantage-x
#!/usr/bin/env bash
/usr/lib/vantage-x/vantagex-gui.py "\$@"
LAUNCHER
chmod +x /usr/bin/vantage-x

echo "Creating Systemd service..."
cat << 'SERVICE' > /etc/systemd/system/vantage-x-daemon.service
[Unit]
Description=Vantage-X Hardware Control Daemon
After=dbus.service

[Service]
Type=simple
ExecStart=/usr/lib/vantage-x/vantagex-daemon.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
SERVICE

echo "Enabling and starting daemon..."
systemctl daemon-reload
systemctl enable --now vantage-x-daemon.service

echo ""
echo "=========================================================="
echo "Installation Complete!"
echo "Daemon is running as root via systemd."
echo ""
echo "You can launch the GUI as your normal user by running:"
echo "  vantage-x"
echo ""
echo "Check daemon logs with:"
echo "  sudo journalctl -fu vantage-x-daemon"
echo "=========================================================="
