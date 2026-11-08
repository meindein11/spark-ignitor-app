import random
import threading
import time
import numpy as np
from .analysis import compute_metrics, stats_batch
from .arduino import Arduino, SimArduino
from .errors import Stopped, TripError
from .rigol import Rigol, SimRigol
from .safety import Safety
from .scope import make_scope
from .storage import Session


class Rig:
    """Owns the three devices and runs shots, batches and sweeps. The dashboard only reads `state`."""

    def __init__(self, cfg, root=None):
        self.cfg = cfg
        self.root = root or cfg.data_dir
        self.stop_evt = threading.Event()
        self.arduino = self.rigol = self.scope = self.session = None
        self.safety = Safety(cfg)
        self.thread = None
        self._hb_run = False
        self._vread = None
        self._batch_id = 0
        self.state = self._fresh_state()

    @staticmethod
    def _fresh_state():
        return dict(status="Disconnected", connected=dict(rigol=False, arduino=False, scope=False), armed=False,
                    trip=False, reason="", busy=False, shot=0, last=None, wave=None, stats=None,
                    sweep=None, progress="", log=[], sim=True)

    # ------------------------------------------------------------------ helpers
    def log(self, msg):
        self.state["log"].append(f"{time.strftime('%H:%M:%S')}  {msg}")

    def _settle(self):
        if self.cfg.rigol_mode != "sim":
            time.sleep(self.cfg.settle_s)

    def _safe_state(self):
        for name, fn in (("Arduino", lambda: self.arduino and self.arduino.disarm()),
                         ("Rigol", lambda: self.rigol and self.rigol.output(False))):
            try:
                fn()
            except Exception as e:
                self.log(f"warning: could not switch off {name}: {e}")
        self.state["armed"] = False

    def _trip(self, reason):
        self.state.update(trip=True, reason=reason, status="TRIPPED")
        self.log(f"TRIP: {reason}")
        self._safe_state()

    # ------------------------------------------------------------------ connection
    def connect(self):
        if self.state["connected"]["arduino"]:
            return
        cfg = self.cfg
        self.arduino = SimArduino() if cfg.arduino_mode == "sim" else Arduino(cfg.arduino_port)
        self.rigol = SimRigol() if cfg.rigol_mode == "sim" else Rigol(cfg.rigol_resource)
        self.scope = make_scope(cfg)
        try:
            self.rigol.open(); self.rigol.protect(cfg.ovp_V); self.rigol.output(False)
            self.state["connected"]["rigol"] = True; self.log(f"Rigol connected ({getattr(self.rigol, 'idn', '')})")
            self.arduino.open()
            self.state["connected"]["arduino"] = True; self.log("Arduino connected")
            self.scope.open()
            self.state["connected"]["scope"] = True; self.log("Scope connected" if cfg.scope_mode != "sim" else "Scope simulated")
        except Exception as e:
            self.log(f"connect failed: {e}")
            self.disconnect()
            raise
        self.session = Session(self.root, cfg)
        self.safety.reset()
        self.state.update(status="Idle", shot=0, last=None, wave=None, stats=None, sweep=None, trip=False, reason="",
                          sim=cfg.all_sim)
        self.log(f"Data folder: {self.session.dir}")
        self._hb_run = True
        threading.Thread(target=self._heartbeat, daemon=True).start()

    def disconnect(self):
        self.stop()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        self._hb_run = False
        self._safe_state()
        for dev in (self.arduino, self.rigol, self.scope):
            try:
                dev and dev.close()
            except Exception as e:
                self.log(f"warning while closing: {e}")
        if self.session:
            self.session.close()
        self.state["connected"] = dict(rigol=False, arduino=False, scope=False)
        self.state["status"] = "Disconnected"

    def _heartbeat(self):
        while self._hb_run:
            time.sleep(1.0)
            if self.state["armed"]:
                try:
                    if not self.arduino.heartbeat():
                        raise RuntimeError("bad heartbeat reply")
                except Exception as e:
                    self._trip(f"Arduino did not answer the heartbeat ({e})")

    # ------------------------------------------------------------------ jobs
    def stop(self):
        self.stop_evt.set()

    def reset_trip(self):
        self.state.update(trip=False, reason="", status="Idle" if self.state["connected"]["arduino"] else "Disconnected")
        self.safety.reset()

    def start_job(self, fn, *args):
        if self.state["busy"]:
            raise RuntimeError("a run is already in progress")
        if not self.state["connected"]["arduino"]:
            raise RuntimeError("connect first")
        if self.state["trip"]:
            raise RuntimeError("a trip is active: press Reset trip first")
        self.stop_evt.clear()
        self.state.update(busy=True, status="Running")

        def run():
            try:
                fn(*args)
            except Stopped:
                self.log("stopped by the operator")
            except TripError as e:
                self._trip(str(e))
            except Exception as e:
                self._trip(f"{type(e).__name__}: {e}")
            finally:
                self._safe_state()
                self.state.update(busy=False, progress="")
                if not self.state["trip"]:
                    self.state["status"] = "Idle"
        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        return self.thread

    # ------------------------------------------------------------------ the physics of one run
    def _prepare(self, vset, dwell):
        reason = self.safety.check_setpoint(vset, dwell)
        if reason:
            raise TripError(reason)
        self.rigol.set(vset, self.cfg.current_limit_A)
        self.arduino.set_dwell(dwell)
        if not self.state["armed"]:
            self.rigol.output(True)
            self._settle()
            self.arduino.arm()
            self.state["armed"] = True
        else:
            self._settle()
        self._vread = None

    def _shot(self, vset, dwell, batch):
        if self.stop_evt.is_set():
            raise Stopped()
        c = self.cfg
        self.scope.start(vset, dwell)
        self.arduino.fire()
        data = self.scope.read(timeout=2.0)
        shot = self.state["shot"] + 1
        if self._vread is None or shot % 5 == 0:
            self._vread = self.rigol.measure()[0]
        if getattr(self.arduino, "watchdog_tripped", False):
            raise TripError("the Arduino watchdog disarmed the trigger")
        m = compute_metrics(data["i_coil"], data["i_spark"], data["dt"], vset, c)
        row = dict(shot=shot, time=time.strftime("%H:%M:%S"), batch=batch, vset_V=vset, vread_V=self._vread,
                   dwell_us=dwell, ipk_A=m["ipk_A"], E_mJ=m["E_mJ"], L_est_mH=m["L_est_mH"], burn_ms=m["burn_ms"],
                   ispark_max_mA=m["ispark_max_mA"], misfire=m["misfire"])
        self.session.add_shot(row, data)
        step = max(1, len(data["i_coil"]) // 1000)
        t = (np.arange(len(data["i_coil"])) * data["dt"] * 1e3)[::step]
        self.state.update(shot=shot, last=row, wave=dict(t=t.round(4).tolist(), coil=data["i_coil"][::step].round(4).tolist(),
                                                         spark=(data["i_spark"][::step] * 1e3).round(3).tolist()))
        reason = self.safety.check_shot(m["ipk_A"], m["misfire"], vset, self._vread)
        if reason:
            raise TripError(reason)
        slept = 0.0
        while slept < c.min_rest_s:                           # rest, but stay responsive to STOP
            time.sleep(min(0.05, c.min_rest_s - slept)); slept += 0.05
            if self.stop_evt.is_set():
                break
        return row

    def _new_batch(self):
        self._batch_id += 1
        return self._batch_id

    def run_batch(self, vset, dwell, n):
        self.log(f"batch: {n} shots at {vset:g} V, {dwell:g} us")
        self.safety.reset()
        self._prepare(vset, dwell)
        batch, rows = self._new_batch(), []
        for i in range(int(n)):
            rows.append(self._shot(vset, dwell, batch))
            self.state.update(stats=stats_batch(rows), progress=f"shot {i + 1} of {int(n)}")
        s = stats_batch(rows)
        self.log(f"batch done: mean E {s['mean_E']:.1f} mJ, SD {s['sd_E']:.1f}, misfires {s['misfires']} of {s['n']}")

    def run_auto(self, vset, dwell):
        self.log(f"auto-fire at {vset:g} V, {dwell:g} us (press STOP to end)")
        self.safety.reset()
        self._prepare(vset, dwell)
        batch, rows = self._new_batch(), []
        while True:
            rows.append(self._shot(vset, dwell, batch))
            self.state.update(stats=stats_batch(rows[-100:]), progress=f"{len(rows)} shots")

    def run_sweep(self, volts, dwells, n, shuffle=True):
        volts, dwells, n = list(volts), list(dwells), int(n)
        shape = (len(dwells), len(volts))
        mean_E, sd_E, rate = (np.full(shape, np.nan) for _ in range(3))
        order = [(di, vi) for di in range(shape[0]) for vi in range(shape[1])]
        if shuffle:
            random.shuffle(order)                             # stops coil heating from biasing one end of the map
        self.log(f"sweep: {len(order)} points x {n} shots (random order: {shuffle})")
        for k, (di, vi) in enumerate(order):
            v, d = volts[vi], dwells[di]
            self.safety.reset()
            self._prepare(v, d)
            batch, rows = self._new_batch(), []
            for _ in range(n):
                rows.append(self._shot(v, d, batch))
            s = stats_batch(rows)
            mean_E[di, vi], sd_E[di, vi], rate[di, vi] = s["mean_E"], s["sd_E"], s["misfire_rate"]
            self.state.update(progress=f"sweep point {k + 1} of {len(order)}", stats=s,
                              sweep=dict(volts=volts, dwells=dwells, mean_E=mean_E.copy(), sd_E=sd_E.copy(), rate=rate.copy()))
        self.session.save_sweep(volts, dwells, mean_E, sd_E, rate, n)
        self.log("sweep finished")
