import threading
import time
from .errors import DeviceError


class ArduinoError(DeviceError):
    pass


def _expect(reply, prefix):
    if not reply.startswith(prefix):
        raise ArduinoError(f"unexpected Arduino reply '{reply}' (expected '{prefix}...')")


class Arduino:
    """Talks to the trigger firmware over serial (115200 baud, one text line per command)."""

    def __init__(self, port="COM3", baud=115200, serial_obj=None, boot_wait=2.0):
        self.port, self.baud, self.ser, self.boot_wait = port, baud, serial_obj, boot_wait
        self._lock = threading.Lock()
        self.watchdog_tripped = False
        self.armed = False

    def open(self):
        if self.ser is None:
            import serial
            self.ser = serial.Serial(self.port, self.baud, timeout=1.0)
        time.sleep(self.boot_wait)          # the Arduino restarts when the port opens
        self.ser.reset_input_buffer()       # throw away the word READY

    def send(self, cmd):
        with self._lock:
            self.ser.write((cmd + "\n").encode())
            for _ in range(4):
                line = self.ser.readline().decode(errors="replace").strip()
                if not line:
                    raise ArduinoError(f"no reply to '{cmd}'")
                if line.startswith("WDG"):          # the watchdog disarmed it earlier
                    self.watchdog_tripped = True
                    self.armed = False
                    continue
                if line.startswith("ERR"):
                    raise ArduinoError(f"Arduino refused '{cmd}': {line}")
                return line
            raise ArduinoError("too many unexpected lines from the Arduino")

    def set_dwell(self, us):
        _expect(self.send(f"D {int(us)}"), "OK D")

    def arm(self):
        self.watchdog_tripped = False
        _expect(self.send("A"), "OK ARMED")
        self.armed = True

    def disarm(self):
        _expect(self.send("X"), "OK SAFE")
        self.armed = False

    def fire(self):
        _expect(self.send("F"), "OK FIRED")

    def heartbeat(self):
        return self.send("?").startswith("D ")

    def close(self):
        try:
            self.disarm()
        except Exception:
            pass
        try:
            self.ser.close()
        except Exception:
            pass


class SimArduino:
    """Same interface, no hardware."""

    def __init__(self, **_):
        self.dwell, self.armed, self.watchdog_tripped = 1000, False, False

    def open(self): pass
    def close(self): self.armed = False

    def set_dwell(self, us):
        if not 100 <= int(us) <= 5000:
            raise ArduinoError("Arduino refused 'D': ERR range")
        self.dwell = int(us)

    def arm(self): self.armed = True
    def disarm(self): self.armed = False

    def fire(self):
        if not self.armed:
            raise ArduinoError("Arduino refused 'F': ERR not armed")

    def heartbeat(self): return True
