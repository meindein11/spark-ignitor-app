import ctypes
import importlib
import time
import numpy as np
from .errors import DeviceError, ScopeTimeout


class SimScope:
    """Makes fake waveforms from a simple coil model. Same interface as PicoScope."""

    def __init__(self, cfg, rng=None):
        self.cfg = cfg
        self.rng = rng or np.random.default_rng()
        self._p = None

    def open(self): pass
    def close(self): pass

    def start(self, vset, dwell_us, auto_trigger_ms=0):
        self._p = (vset, dwell_us)

    def read(self, timeout=2.0):
        c = self.cfg
        vset, dwell_us = self._p
        dt = c.sample_interval_us * 1e-6
        n = int(c.window_ms * 1e-3 / dt)
        t = np.arange(n) * dt
        t0 = c.pretrigger_frac * c.window_ms * 1e-3
        dwell = dwell_us * 1e-6
        L = c.L_mH * 1e-3
        amp = 1.0 + self.rng.normal(0, 0.01)                       # shot to shot variation
        charging = (t >= t0) & (t < t0 + dwell)
        i_coil = np.where(charging, vset / c.R_ohm * (1 - np.exp(-(t - t0) * c.R_ohm / L)), 0.0) * amp
        ipk = vset / c.R_ohm * (1 - np.exp(-dwell * c.R_ohm / L)) * amp
        energy_mJ = 0.5 * c.L_mH * ipk ** 2
        i_spark = np.zeros(n)
        if energy_mJ >= 15.0:                                      # simple rule: enough energy, spark
            burn = energy_mJ / 45.0 * 1e-3
            t1 = t0 + dwell
            s = (t >= t1) & (t < t1 + burn)
            i_spark[s] = 0.06 * (1 - (t[s] - t1) / burn)
        i_coil = i_coil + self.rng.normal(0, 0.03, n)
        i_spark = i_spark + self.rng.normal(0, 0.0015, n)
        return dict(dt=dt, i_coil=i_coil, i_spark=i_spark)


class PicoScope:
    """PicoScope 2000A / 3000A / 5000A series through Pico's Python wrappers (picosdk).

    NOT TESTED ON HARDWARE. It follows Pico's published block-mode example and the function signatures
    of the installed picosdk package. Check it first with:  python -m spark_ignitor scope-test
    Channel A = coil current (current clamp), channel B = spark current (voltage across R_SH).
    """

    def __init__(self, cfg, series="ps2000a"):
        self.cfg, self.series = cfg, series
        self.P = series.upper()
        self.h = ctypes.c_int16()
        self.range_A = self.range_B = None
        self._opened = False

    def _fn(self, name):
        return getattr(self.ps, f"{self.series}{name}")

    def _enum(self, table, key):
        return getattr(self.ps, f"{self.P}_{table}")[f"{self.P}_{key}"]

    def open(self):
        try:
            self.ps = getattr(importlib.import_module(f"picosdk.{self.series}"), self.series)
            from picosdk.functions import assert_pico_ok, adc2mV, mV2adc
        except Exception as e:
            raise DeviceError(f"cannot load the PicoSDK for {self.series}: {e}. Install the PicoSDK "
                              f"(same 32/64-bit as Python) and close PicoScope 7.")
        self._assert, self._adc2mV, self._mV2adc = assert_pico_ok, adc2mV, mV2adc
        if self.series == "ps5000a":                               # 5000 series: pick 8-bit mode (fastest, simple timebase)
            st = self._fn("OpenUnit")(ctypes.byref(self.h), None, self._enum("DEVICE_RESOLUTION", "DR_8BIT"))
        else:
            st = self._fn("OpenUnit")(ctypes.byref(self.h), None)
        if st in (282, 286):                                       # USB power messages
            change = getattr(self.ps, f"{self.series}ChangePowerSource", None)
            if change is None:
                raise DeviceError(f"scope reports power status {st} and this wrapper cannot change it")
            st = change(self.h, st)
        self._assert(st)
        self._opened = True
        c = self.cfg
        self.range_A = self._enum("RANGE", c.range_A.upper())
        self.range_B = self._enum("RANGE", c.range_B.upper())
        coupling = self._enum("COUPLING", "DC")
        for ch, rng in (("A", self.range_A), ("B", self.range_B)):
            self._assert(self._fn("SetChannel")(self.h, self._enum("CHANNEL", f"CHANNEL_{ch}"), 1, coupling, rng, 0.0))
        self.maxADC = ctypes.c_int16()
        self._assert(self._fn("MaximumValue")(self.h, ctypes.byref(self.maxADC)))
        # timebase: the nearest valid sample interval (about 8 ns steps on these series)
        n = max(3, int(round(c.sample_interval_us * 1000 / 8)) + 2)
        self.samples = int(c.window_ms * 1000 / c.sample_interval_us)
        for _ in range(40):
            interval = ctypes.c_float()
            max_samples = ctypes.c_int32()
            if self.series == "ps5000a":                           # no 'oversample' argument on the 5000 series
                st = self._fn("GetTimebase2")(self.h, n, self.samples, ctypes.byref(interval), ctypes.byref(max_samples), 0)
            else:
                st = self._fn("GetTimebase2")(self.h, n, self.samples, ctypes.byref(interval), 1, ctypes.byref(max_samples), 0)
            if st == 0:
                break
            n += 1
        self._assert(st)
        self.timebase, self.dt = n, interval.value * 1e-9

    def close(self):
        if self._opened:
            try:
                self._fn("Stop")(self.h)
            finally:
                self._assert(self._fn("CloseUnit")(self.h))
                self._opened = False

    def start(self, vset=None, dwell_us=None, auto_trigger_ms=0):
        c = self.cfg
        thr = int(self._mV2adc(c.trigger_level_V * 1000.0, self.range_A, self.maxADC))
        self._assert(self._fn("SetSimpleTrigger")(self.h, 1, self._enum("CHANNEL", "CHANNEL_A"), thr,
                                                  self._enum("THRESHOLD_DIRECTION", "RISING"), 0, int(auto_trigger_ms)))
        pre = int(self.samples * c.pretrigger_frac)
        post = self.samples - pre
        if self.series == "ps5000a":
            self._assert(self._fn("RunBlock")(self.h, pre, post, self.timebase, None, 0, None, None))
        else:
            self._assert(self._fn("RunBlock")(self.h, pre, post, self.timebase, 1, None, 0, None, None))

    def read(self, timeout=2.0):
        ready = ctypes.c_int16(0)
        t_end = time.time() + timeout
        while not ready.value:
            self._assert(self._fn("IsReady")(self.h, ctypes.byref(ready)))
            if time.time() > t_end:
                self._fn("Stop")(self.h)
                raise ScopeTimeout("the scope saw no trigger (check the clamp, the trigger level and the range)")
            time.sleep(0.002)
        none = self._enum("RATIO_MODE", "RATIO_MODE_NONE")
        bufs = {}
        for ch in ("A", "B"):
            mx = (ctypes.c_int16 * self.samples)()
            mn = (ctypes.c_int16 * self.samples)()
            self._assert(self._fn("SetDataBuffers")(self.h, self._enum("CHANNEL", f"CHANNEL_{ch}"),
                                                    ctypes.byref(mx), ctypes.byref(mn), self.samples, 0, none))
            bufs[ch] = mx
        n = ctypes.c_int32(self.samples)
        overflow = ctypes.c_int16()
        self._assert(self._fn("GetValues")(self.h, 0, ctypes.byref(n), 1, none, 0, ctypes.byref(overflow)))
        volts_A = np.array(self._adc2mV(bufs["A"], self.range_A, self.maxADC)[:n.value]) / 1000.0
        volts_B = np.array(self._adc2mV(bufs["B"], self.range_B, self.maxADC)[:n.value]) / 1000.0
        return dict(dt=self.dt, i_coil=volts_A / self.cfg.clamp_V_per_A, i_spark=volts_B / self.cfg.shunt_ohm)


def make_scope(cfg):
    if cfg.scope_mode == "sim":
        return SimScope(cfg)
    return PicoScope(cfg, series=cfg.scope_mode)


def check_connected():
    """Find out which PicoScope is connected and which driver series it needs."""
    from picosdk.discover import find_unit
    dev = find_unit()
    try:
        info = dev.info
    except Exception:
        info = "(no extra information available)"
    name = getattr(dev.driver, "name", "unknown")
    dev.close()
    return name, info
