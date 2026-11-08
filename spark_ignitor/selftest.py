"""Checks that need no hardware. Run with:  python -m spark_ignitor selftest"""
import io
import tempfile
import time
import zipfile
from collections import deque
import numpy as np
from .analysis import compute_metrics, stats_batch
from .arduino import Arduino, ArduinoError
from .config import Config
from .errors import TripError
from .rig import Rig
from .rigol import Rigol, RigolError
from .safety import Safety
from .scope import SimScope


class MockArduinoSerial:
    """Behaves like the firmware in firmware/spark_trigger/spark_trigger.ino, including the watchdog."""
    def __init__(self):
        self.out, self.dwell, self.armed, self.t, self.last = deque(), 1000, False, 0.0, 0.0
        self.fired = 0
    def reset_input_buffer(self): self.out.clear()
    def close(self): pass
    def readline(self): return (self.out.popleft() if self.out else b"")
    def write(self, b):
        if self.armed and self.t - self.last > 3.0:
            self.armed = False; self.out.append(b"WDG SAFE\n")
        s = b.decode().strip(); self.last = self.t; r = "ERR unknown"
        if s.startswith("D "):
            v = int(s[2:]); r = "OK D" if 100 <= v <= 5000 else "ERR range"
            if r == "OK D": self.dwell = v
        elif s == "A": self.armed = True; r = "OK ARMED"
        elif s == "X": self.armed = False; r = "OK SAFE"
        elif s == "F": r = "OK FIRED" if self.armed else "ERR not armed"; self.fired += (r == "OK FIRED")
        elif s == "?": r = f"D {self.dwell}"
        self.out.append((r + "\n").encode())


class MockRes:
    def __init__(self, bad=False): self.sent, self.bad = [], bad; self.timeout = None
    def write(self, c): self.sent.append(c)
    def close(self): pass
    def query(self, c):
        if c == "*IDN?": return "RIGOL TECHNOLOGIES,DP832A,DP8A000000,00.01\n"
        if c == ":SYST:ERR?": return '-113,"Undefined header"' if self.bad else '0,"No error"'
        if c.startswith(":MEAS:VOLT?"): return "11.998"
        if c.startswith(":MEAS:CURR?"): return "0.052"
        raise AssertionError(c)


def _cfg(tmp, **kw):
    return Config(min_rest_s=0.0, data_dir=tmp, **kw)


def test_physics_good_shot():
    cfg = Config(); sc = SimScope(cfg, np.random.default_rng(1)); sc.start(12, 2000); d = sc.read()
    m = compute_metrics(d["i_coil"], d["i_spark"], d["dt"], 12, cfg)
    assert 6.3 < m["ipk_A"] < 7.3, m          # hand calculation: 6.8 A
    assert 60 < m["E_mJ"] < 80, m             # hand calculation: 69 mJ
    assert 1.2 < m["burn_ms"] < 1.8 and not m["misfire"], m
    assert 2.5 < m["L_est_mH"] < 4.0, m


def test_physics_misfire():
    cfg = Config(); sc = SimScope(cfg, np.random.default_rng(2)); sc.start(12, 800); d = sc.read()
    m = compute_metrics(d["i_coil"], d["i_spark"], d["dt"], 12, cfg)
    assert m["misfire"] and m["burn_ms"] == 0, m


def test_safety():
    s = Safety(Config())
    assert s.check_setpoint(12, 6000) and s.check_setpoint(20, 2000) and not s.check_setpoint(12, 2000)
    assert s.check_shot(20.0, False, 12, 12) and s.check_shot(5.0, False, 12, 9.0)
    s.reset()
    assert all(s.check_shot(5, True, 12, 12) is None for _ in range(9)) and "misfires" in s.check_shot(5, True, 12, 12)


def test_arduino_protocol():
    mock = MockArduinoSerial(); a = Arduino(serial_obj=mock, boot_wait=0); a.open()
    try: a.fire(); raise SystemExit("fire while disarmed must fail")
    except ArduinoError as e: assert "not armed" in str(e)
    try: a.set_dwell(9000); raise SystemExit("range check missing")
    except ArduinoError as e: assert "range" in str(e)
    a.set_dwell(2000); a.arm(); a.fire(); assert mock.fired == 1 and a.heartbeat()
    mock.t += 4.0                                   # the PC goes silent for 4 s
    try: a.fire(); raise SystemExit("watchdog must disarm")
    except ArduinoError: pass
    assert a.watchdog_tripped and not a.armed
    a.close()


def test_rigol_commands():
    r = MockRes(); g = Rigol(res_obj=r); g.open(); g.protect(14); g.set(12, 3); g.output(True)
    assert r.sent == [":OUTP:OVP:VAL CH1,14.000", ":OUTP:OVP CH1,ON", ":APPL CH1,12.000,3.000", ":OUTP CH1,ON"], r.sent
    assert g.measure() == (11.998, 0.052)
    try: Rigol(res_obj=MockRes(bad=True)).open() or Rigol(res_obj=MockRes(bad=True))._write(":X"); raise SystemExit("error must be raised")
    except RigolError: pass


def test_batch_and_trip():
    with tempfile.TemporaryDirectory() as tmp:
        rig = Rig(_cfg(tmp)); rig.connect(); rig.run_batch(12, 2000, 12)
        s = rig.state["stats"]; assert s["n"] == 12 and s["misfires"] == 0 and 60 < s["mean_E"] < 80, s
        assert len(rig.session.rows) == 12 and (rig.session.dir / "shots.csv").exists()
        rig.disconnect()
        rig = Rig(_cfg(tmp, I_trip_A=3.0)); rig.connect(); rig.start_job(rig.run_batch, 12, 2000, 5).join(10)
        assert rig.state["trip"] and "peak current" in rig.state["reason"], rig.state["reason"]
        assert not rig.arduino.armed and not rig.rigol.on                  # everything switched off
        rig.disconnect()
        rig = Rig(_cfg(tmp)); rig.connect(); rig.start_job(rig.run_batch, 12, 6000, 5).join(10)
        assert rig.state["trip"] and "dwell" in rig.state["reason"]
        rig.disconnect()


def test_sweep_and_exports():
    with tempfile.TemporaryDirectory() as tmp:
        rig = Rig(_cfg(tmp, waveform_every=3)); rig.connect()
        rig.run_sweep([8, 10, 12], [800, 2000, 3000], 5)
        sw = rig.state["sweep"]; assert sw["mean_E"].shape == (3, 3)
        assert np.allclose(sw["rate"][0], 1.0) and np.allclose(sw["rate"][1:], 0.0), sw["rate"]   # only 800 us misfires
        assert 25 < sw["mean_E"][1, 0] < 35 and 55 < sw["mean_E"][2, 0] < 66                       # 8 V: 30 mJ and 60 mJ
        ss = rig.session
        assert ss.csv_bytes().count(b"\n") == 46                                                  # header + 45 shots
        assert ss.pdf_bytes()[:4] == b"%PDF"
        z = zipfile.ZipFile(io.BytesIO(ss.pngs_zip_bytes())); assert len(z.namelist()) == 5, z.namelist()
        z = zipfile.ZipFile(io.BytesIO(ss.waveforms_zip_bytes())); assert any(n.endswith(".npz") for n in z.namelist())
        z = zipfile.ZipFile(io.BytesIO(ss.bundle_bytes())); names = z.namelist()
        assert "report.pdf" in names and "shots.csv" in names and "sweep.csv" in names, names
        rig.disconnect()


TESTS = [test_physics_good_shot, test_physics_misfire, test_safety, test_arduino_protocol, test_rigol_commands,
         test_batch_and_trip, test_sweep_and_exports]


def run_all():
    ok = True
    for t in TESTS:
        t0 = time.time()
        try:
            t(); print(f"  PASS  {t.__name__}  ({time.time() - t0:.1f} s)")
        except BaseException as e:
            ok = False; print(f"  FAIL  {t.__name__}: {type(e).__name__}: {e}")
    print("ALL TESTS PASSED" if ok else "SOME TESTS FAILED")
    return ok
