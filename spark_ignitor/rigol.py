import random
import time
from .errors import DeviceError


class RigolError(DeviceError):
    pass


class Rigol:
    """Rigol DP800 series over VISA (USB). Channel 1 only."""

    def __init__(self, resource="", res_obj=None, channel="CH1"):
        self.resource, self.res, self.ch = resource, res_obj, channel

    def open(self):
        if self.res is None:
            import pyvisa
            rm = pyvisa.ResourceManager()
            self.res = rm.open_resource(self.resource)
        self.res.timeout = 3000
        self.res.write_termination = "\n"
        self.res.read_termination = "\n"
        self.idn = self.res.query("*IDN?").strip()
        if "DP8" not in self.idn:
            raise RigolError(f"this does not look like a Rigol DP800: '{self.idn}'")

    def _write(self, cmd):
        self.res.write(cmd)
        err = self.res.query(":SYST:ERR?").strip()      # the supply reports a bad command here
        if not err.startswith("0"):
            raise RigolError(f"Rigol rejected '{cmd}': {err}")

    def protect(self, ovp_V):
        self._write(f":OUTP:OVP:VAL {self.ch},{ovp_V:.3f}")
        self._write(f":OUTP:OVP {self.ch},ON")

    def set(self, volts, amps):
        self._write(f":APPL {self.ch},{volts:.3f},{amps:.3f}")

    def output(self, on):
        self._write(f":OUTP {self.ch},{'ON' if on else 'OFF'}")

    def measure(self):
        v = float(self.res.query(f":MEAS:VOLT? {self.ch}"))
        i = float(self.res.query(f":MEAS:CURR? {self.ch}"))
        return v, i

    def close(self):
        try:
            self.output(False)
        finally:
            try:
                self.res.close()
            except Exception:
                pass


class SimRigol:
    def __init__(self, **_):
        self.v, self.i, self.on = 0.0, 3.0, False

    def open(self): self.idn = "SIMULATED,DP832A"
    def protect(self, ovp_V): self.ovp = ovp_V

    def set(self, volts, amps):
        self.v, self.i = volts, amps

    def output(self, on): self.on = bool(on)

    def measure(self):
        return (self.v + random.gauss(0, 0.01) if self.on else 0.0), (0.05 if self.on else 0.0)

    def close(self): self.on = False
