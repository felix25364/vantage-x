#!/usr/bin/env python3
import sys
import asyncio
import signal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlApplicationEngine
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from qasync import QEventLoop
from dbus_next.aio import MessageBus

class DBusBackend(QObject):
    # Signale an QML, um die Oberfläche zu aktualisieren
    chargeStartUpdated = pyqtSignal(int, arguments=['threshold'])
    chargeEndUpdated = pyqtSignal(int, arguments=['threshold'])
    penPercentageUpdated = pyqtSignal(int, arguments=['percentage'])
    powerProfileUpdated = pyqtSignal(str, arguments=['profile'])

    def __init__(self):
        super().__init__()
        self.bus = None
        self.proxy_interface = None

    async def init_dbus(self):
        try:
            # Verbindung zum System Bus (wo der Daemon läuft)
            self.bus = await MessageBus(bus_type=0).connect()
            
            # Introspektion und Proxy-Objekt holen
            introspection = await self.bus.introspect('org.vantagex.daemon', '/org/vantagex/daemon')
            proxy_object = self.bus.get_proxy_object('org.vantagex.daemon', '/org/vantagex/daemon', introspection)
            self.proxy_interface = proxy_object.get_interface('org.vantagex.daemon')

            # Initiale Werte abfragen und an QML senden
            start = await self.proxy_interface.call_get_charge_start_threshold()
            end = await self.proxy_interface.call_get_charge_end_threshold()
            pen = await self.proxy_interface.call_get_pen_percentage()
            profile = await self.proxy_interface.call_get_active_profile()

            self.chargeStartUpdated.emit(start)
            self.chargeEndUpdated.emit(end)
            self.penPercentageUpdated.emit(pen)
            self.powerProfileUpdated.emit(profile)

            # Auf D-Bus-Signale vom Daemon horchen
            self.proxy_interface.on_pen_percentage_changed(self.penPercentageUpdated.emit)
            self.proxy_interface.on_power_profile_changed(self.powerProfileUpdated.emit)
            # Falls benötigt, könnte hier auch TabletMode überwacht werden

        except Exception as e:
            print(f"Fehler bei der D-Bus Initialisierung: {e}", file=sys.stderr)

    # Slots, die von QML aufgerufen werden (z.B. durch Slider/Buttons)
    @pyqtSlot(int)
    def setChargeStartThreshold(self, threshold):
        if self.proxy_interface:
            asyncio.create_task(self.proxy_interface.call_set_charge_start_threshold(threshold))

    @pyqtSlot(int)
    def setChargeEndThreshold(self, threshold):
        if self.proxy_interface:
            asyncio.create_task(self.proxy_interface.call_set_charge_end_threshold(threshold))

    @pyqtSlot(str)
    def setPowerProfile(self, profile):
        if self.proxy_interface:
            asyncio.create_task(self.proxy_interface.call_set_active_profile(profile))


def main():
    app = QGuiApplication(sys.argv)

    # Hier nutzen wir qasync, um die Event-Loop sauber aufzusetzen
    # Das verhindert den RuntimeError in Python 3.10+
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    engine = QQmlApplicationEngine()
    backend = DBusBackend()

    # Kontext-Eigenschaft setzen, damit Dashboard.qml auf 'dbusBackend' zugreifen kann
    engine.rootContext().setContextProperty("dbusBackend", backend)

    # QML-Datei laden (Pfad passt sich an die Installation an)
    qml_path = os.path.join(os.path.dirname(__file__), "Dashboard.qml")
    if not os.path.exists(qml_path):
        qml_path = "/usr/lib/vantage-x/Dashboard.qml"

    engine.load(qml_path)

    if not engine.rootObjects():
        sys.exit(-1)

    # Hauptfenster sichtbar machen, sobald alles geladen ist
    engine.rootObjects()[0].setVisible(True)

    # D-Bus asynchron nach dem Start der Loop initialisieren
    loop.create_task(backend.init_dbus())

    # Sauberes Beenden bei SIGINT (Ctrl+C)
    def ask_exit():
        loop.stop()

    for signame in ('SIGINT', 'SIGTERM'):
        try:
            loop.add_signal_handler(getattr(signal, signame), ask_exit)
        except NotImplementedError:
            pass # Falls auf Windows, aber wir sind auf Arch

    with loop:
        loop.run_forever()

if __name__ == "__main__":
    import os
    main()
