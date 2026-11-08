from dataclasses import dataclass, asdict, fields
import json
from pathlib import Path


@dataclass
class Config:
    # ---- coil and measurement (replace with your measured values)
    L_mH: float = 3.0              # primary inductance (team estimate)
    R_ohm: float = 0.5             # primary resistance (team estimate)
    clamp_V_per_A: float = 0.1     # current clamp scale: check the range switch on the clamp
    shunt_ohm: float = 10.0        # R_SH in the plug ground lead
    # ---- limits that stop a run
    I_trip_A: float = 12.0
    spark_threshold_A: float = 0.01
    max_dwell_us: int = 5000       # same limit as the Arduino firmware
    max_voltage_V: float = 16.0
    misfires_to_trip: int = 10
    vread_tolerance_V: float = 1.0
    # ---- power supply
    ovp_V: float = 14.0            # over-voltage trip set in the Rigol
    current_limit_A: float = 3.0
    # ---- capture
    window_ms: float = 10.0
    sample_interval_us: float = 2.0
    pretrigger_frac: float = 0.10
    trigger_level_V: float = 0.05  # on scope channel A (0.5 A with a 0.1 V/A clamp)
    range_A: str = "2V"
    range_B: str = "2V"
    # ---- timing
    min_rest_s: float = 0.2        # rest between shots (coil heating)
    settle_s: float = 0.3          # wait after switching the Rigol output on
    # ---- devices
    arduino_mode: str = "sim"      # sim | real
    arduino_port: str = "COM3"
    rigol_mode: str = "sim"        # sim | real
    rigol_resource: str = ""       # for example USB0::0x1AB1::0x0E11::DP8...::INSTR
    scope_mode: str = "sim"        # sim | ps2000a | ps3000a
    # ---- files
    data_dir: str = "data"
    waveform_every: int = 10       # save raw waveforms of every Nth shot

    @property
    def all_sim(self):
        return self.arduino_mode == "sim" and self.rigol_mode == "sim" and self.scope_mode == "sim"

    @classmethod
    def load(cls, path):
        p = Path(path)
        if not p.exists():
            return cls()
        raw = json.loads(p.read_text())
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in raw.items() if k in names})

    def save(self, path):
        Path(path).write_text(json.dumps(asdict(self), indent=2))
