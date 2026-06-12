#!/usr/bin/env python3
import sys
import asyncio
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot, QUrl
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtQml import QQmlApplicationEngine
import qasync
from dbus_next.aio import MessageBus
from dbus_next.message import Message

class DBusBackend(QObject):
    # Signals to update QML UI
    penPercentageUpdated = pyqtSignal(int, arguments=['percentage'])
    chargeStartUpdated = pyqtSignal(int, arguments=['threshold'])
    chargeEndUpdated = pyqtSignal(int, arguments=['threshold'])
    powerProfileUpdated = pyqtSignal(str, arguments=['profile'])

    def __init__(self):
        super().__init__()
        self.bus = None
        self.daemon_proxy = None

    async def connect_dbus(self):
        self.bus = await MessageBus(bus_type=0).connect()
        # Initial states
        await self.refresh_all()

        # Listen for signals (Requires introspection or hardcoded match rule, using standard match rule for simplicity)
        self.bus.add_message_handler(self._message_handler)
        await self.bus.call(Message(
            destination='org.freedesktop.DBus',
            path='/org/freedesktop/DBus',
            interface='org.freedesktop.DBus',
            member='AddMatch',
            signature='s',
            body=["type='signal',interface='org.vantagex.daemon'"]
        ))

    def _message_handler(self, msg: Message):
        if msg.interface == 'org.vantagex.daemon':
            if msg.member == 'PenPercentageChanged':
                self.penPercentageUpdated.emit(msg.body[0])
            elif msg.member == 'PowerProfileChanged':
                self.powerProfileUpdated.emit(msg.body[0])

    async def _call_daemon(self, member, signature='', body=None):
        msg = Message(
            destination='org.vantagex.daemon',
            path='/org/vantagex/daemon',
            interface='org.vantagex.daemon',
            member=member,
            signature=signature,
            body=body or []
        )
        return await self.bus.call(msg)

    async def refresh_all(self):
        # Start
        reply = await self._call_daemon('GetChargeStartThreshold')
        if reply and reply.body:
            self.chargeStartUpdated.emit(reply.body[0])
        # End
        reply = await self._call_daemon('GetChargeEndThreshold')
        if reply and reply.body:
            self.chargeEndUpdated.emit(reply.body[0])
        # Pen
        reply = await self._call_daemon('GetPenPercentage')
        if reply and reply.body:
            self.penPercentageUpdated.emit(reply.body[0])
        # Profile
        reply = await self._call_daemon('GetActiveProfile')
        if reply and reply.body:
            self.powerProfileUpdated.emit(reply.body[0])

    @pyqtSlot(int)
    def setChargeStartThreshold(self, threshold):
        asyncio.create_task(self._call_daemon('SetChargeStartThreshold', 'i', [threshold]))

    @pyqtSlot(int)
    def setChargeEndThreshold(self, threshold):
        asyncio.create_task(self._call_daemon('SetChargeEndThreshold', 'i', [threshold]))

    @pyqtSlot(str)
    def setPowerProfile(self, profile):
        asyncio.create_task(self._call_daemon('SetActiveProfile', 's', [profile]))


def main():
    app = QApplication(sys.argv)

    # Material style
    import os
    os.environ["QT_QUICK_CONTROLS_STYLE"] = "Material"

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    backend = DBusBackend()

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("dbusBackend", backend)

    qml_file = os.path.join(os.path.dirname(__file__), 'Dashboard.qml')
    engine.load(QUrl.fromLocalFile(qml_file))

    if not engine.rootObjects():
        sys.exit(-1)

    # Tray Icon
    tray_icon = QSystemTrayIcon(QIcon.fromTheme("preferences-system"), app)
    tray_menu = QMenu()
    show_action = QAction("Show Dashboard", app)

    # Show QML window when requested
    window = engine.rootObjects()[0]
    show_action.triggered.connect(window.show)

    quit_action = QAction("Quit", app)
    quit_action.triggered.connect(app.quit)

    tray_menu.addAction(show_action)
    tray_menu.addAction(quit_action)
    tray_icon.setContextMenu(tray_menu)
    tray_icon.show()

    # Intercept window close to just hide
    def on_closing(close_event):
        close_event.ignore()
        window.hide()

    window.closing.connect(on_closing)

    # Initialize DBus
    asyncio.create_task(backend.connect_dbus())

    with loop:
        loop.run_forever()

if __name__ == '__main__':
    main()
