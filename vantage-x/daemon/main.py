#!/usr/bin/env python3
import asyncio
import glob
import os
import signal
from dbus_next.aio import MessageBus
from dbus_next.service import ServiceInterface, method, signal as dbus_signal
from dbus_next.message import Message, MessageType
import evdev
from evdev import ecodes

class VantageXDaemon(ServiceInterface):
    def __init__(self, name):
        super().__init__(name)
        self.tablet_mode = False
        self.grabbed_devices = []

    def _get_battery_path(self):
        # Dynamically find the primary battery
        paths = glob.glob('/sys/class/power_supply/BAT*')
        if paths:
            return paths[0]
        return None

    def _read_sysfs_int(self, path):
        try:
            with open(path, 'r') as f:
                return int(f.read().strip())
        except (FileNotFoundError, ValueError):
            return -1

    def _write_sysfs_int(self, path, value):
        try:
            with open(path, 'w') as f:
                f.write(str(value))
            return True
        except (FileNotFoundError, PermissionError):
            return False

    @method()
    def GetChargeStartThreshold(self) -> 'i':
        bat_path = self._get_battery_path()
        if bat_path:
            return self._read_sysfs_int(os.path.join(bat_path, 'charge_control_start_threshold'))
        return -1

    @method()
    def SetChargeStartThreshold(self, threshold: 'i'):
        bat_path = self._get_battery_path()
        if bat_path:
            self._write_sysfs_int(os.path.join(bat_path, 'charge_control_start_threshold'), threshold)

    @method()
    def GetChargeEndThreshold(self) -> 'i':
        bat_path = self._get_battery_path()
        if bat_path:
            return self._read_sysfs_int(os.path.join(bat_path, 'charge_control_end_threshold'))
        return -1

    @method()
    def SetChargeEndThreshold(self, threshold: 'i'):
        bat_path = self._get_battery_path()
        if bat_path:
            self._write_sysfs_int(os.path.join(bat_path, 'charge_control_end_threshold'), threshold)

    @method()
    def GetPenPercentage(self) -> 'i':
        # Dynamic discovery for ThinkPad Pen
        globs = [
            '/sys/class/power_supply/hid-openzen*-battery/',
            '/sys/class/power_supply/wacom_battery_*/',
            '/sys/class/power_supply/hid-*-battery/'
        ]
        for pattern in globs:
            paths = glob.glob(pattern)
            for path in paths:
                capacity_file = os.path.join(path, 'capacity')
                val = self._read_sysfs_int(capacity_file)
                if val >= 0:
                    return val
        return -1

    # D-Bus proxy for Power Profiles
    async def _get_power_profiles_proxy(self):
        bus = await MessageBus(bus_type=evdev.ecodes.EV_SW).connect() # Actually we use system bus for all
        return None # We will do proxy directly via dbus_next Message

    @method()
    async def GetActiveProfile(self) -> 's':
        bus = await MessageBus(bus_type=0).connect() # system bus
        msg = Message(destination='net.hadess.PowerProfiles',
                      path='/net/hadess/PowerProfiles',
                      interface='org.freedesktop.DBus.Properties',
                      member='Get',
                      signature='ss',
                      body=['net.hadess.PowerProfiles', 'ActiveProfile'])
        reply = await bus.call(msg)
        bus.disconnect()
        if reply and reply.message_type == MessageType.METHOD_RETURN:
            return reply.body[0].value
        return "balanced"

    @method()
    async def SetActiveProfile(self, profile: 's'):
        bus = await MessageBus(bus_type=0).connect() # system bus
        # Create a variant object for the dbus property
        from dbus_next.signature import Variant
        msg = Message(destination='net.hadess.PowerProfiles',
                      path='/net/hadess/PowerProfiles',
                      interface='org.freedesktop.DBus.Properties',
                      member='Set',
                      signature='ssv',
                      body=['net.hadess.PowerProfiles', 'ActiveProfile', Variant('s', profile)])
        await bus.call(msg)
        bus.disconnect()
        self.PowerProfileChanged(profile)

    @method()
    def ScanMiracast(self) -> 'as':
        # Stub
        return []

    @method()
    def ConnectMiracast(self, target_mac: 's') -> 'b':
        # Stub
        return False

    @dbus_signal()
    def PenPercentageChanged(self, percentage: 'i') -> 'i':
        return percentage

    @dbus_signal()
    def PowerProfileChanged(self, profile: 's') -> 's':
        return profile

    @dbus_signal()
    def TabletModeChanged(self, is_tablet_mode: 'b') -> 'b':
        return is_tablet_mode

    # Input Management for Tablet Mode
    def update_grabs(self):
        if self.tablet_mode:
            # Grab keyboard and touchpad
            for device in [evdev.InputDevice(path) for path in evdev.list_devices()]:
                if "keyboard" in device.name.lower() or "touchpad" in device.name.lower():
                    try:
                        device.grab()
                        self.grabbed_devices.append(device)
                        print(f"Grabbed {device.name}")
                    except IOError:
                        pass
        else:
            # Release grabs
            for device in self.grabbed_devices:
                try:
                    device.ungrab()
                    print(f"Released {device.name}")
                except IOError:
                    pass
            self.grabbed_devices = []

    async def monitor_tablet_mode(self):
        # Find device with SW_TABLET_MODE
        tablet_dev = None
        for path in evdev.list_devices():
            dev = evdev.InputDevice(path)
            if ecodes.EV_SW in dev.capabilities():
                if ecodes.SW_TABLET_MODE in dev.capabilities()[ecodes.EV_SW]:
                    tablet_dev = dev
                    break

        if not tablet_dev:
            print("No tablet mode switch found.")
            return

        print(f"Monitoring tablet mode on {tablet_dev.name}")

        # Initial state
        state = tablet_dev.switch().get(ecodes.SW_TABLET_MODE, 0)
        self.tablet_mode = bool(state)
        self.update_grabs()

        async for event in tablet_dev.async_read_loop():
            if event.type == ecodes.EV_SW and event.code == ecodes.SW_TABLET_MODE:
                self.tablet_mode = bool(event.value)
                print(f"Tablet mode changed to: {self.tablet_mode}")
                self.update_grabs()
                self.TabletModeChanged(self.tablet_mode)

    async def pen_monitor_loop(self):
        last_val = -1
        while True:
            val = self.GetPenPercentage()
            if val != last_val and val >= 0:
                self.PenPercentageChanged(val)
                last_val = val
            await asyncio.sleep(10)

async def main():
    bus = await MessageBus(bus_type=0).connect() # System bus
    daemon = VantageXDaemon('org.vantagex.daemon')
    bus.export('/org/vantagex/daemon', daemon)
    await bus.request_name('org.vantagex.daemon')
    print("Vantage-X Daemon running on System D-Bus")

    # Start background monitors
    asyncio.create_task(daemon.monitor_tablet_mode())
    asyncio.create_task(daemon.pen_monitor_loop())

    # Keep alive
    await asyncio.Future()

if __name__ == '__main__':
    # Ensure clean exit
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: loop.stop())
    try:
        loop.run_until_complete(main())
    except asyncio.CancelledError:
        pass
