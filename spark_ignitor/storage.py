import csv
import io
import json
import time
import zipfile
from dataclasses import asdict
from pathlib import Path
import numpy as np

FIELDS = ["shot", "time", "batch", "vset_V", "vread_V", "dwell_us", "ipk_A", "E_mJ",
          "L_est_mH", "burn_ms", "ispark_max_mA", "misfire"]


class Session:
    """One run = one folder: shots.csv, settings.json, raw waveforms, sweep results, reports."""

    def __init__(self, root, cfg):
        self.cfg = cfg
        self.dir = Path(root) / f"Run_{time.strftime('%Y%m%d_%H%M%S')}"
        (self.dir / "waveforms").mkdir(parents=True, exist_ok=True)
        (self.dir / "settings.json").write_text(json.dumps(asdict(cfg), indent=2))
        self.rows, self.waves, self.sweep, self.last_wave = [], {}, None, None
        self.spark_wave = self.spark_row = None
        self._csv = open(self.dir / "shots.csv", "w", newline="")
        self._w = csv.DictWriter(self._csv, fieldnames=FIELDS)
        self._w.writeheader()

    def add_shot(self, row, wave):
        self.rows.append(row)
        self._w.writerow({k: row.get(k) for k in FIELDS})
        self._csv.flush()
        self.last_wave = wave
        if not row["misfire"]:
            self.spark_wave, self.spark_row = wave, row          # the report shows the latest shot that sparked
        every = max(1, self.cfg.waveform_every)
        if (row["shot"] - 1) % every == 0:
            path = self.dir / "waveforms" / f"shot_{row['shot']:05d}.npz"
            np.savez_compressed(path, dt=wave["dt"], i_coil=wave["i_coil"], i_spark=wave["i_spark"])
            self.waves[row["shot"]] = path

    def save_sweep(self, volts, dwells, mean_E, sd_E, rate, n):
        self.sweep = dict(volts=list(volts), dwells=list(dwells), mean_E=np.array(mean_E),
                          sd_E=np.array(sd_E), rate=np.array(rate), n=n)
        with open(self.dir / "sweep.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["vset_V", "dwell_us", "shots", "mean_E_mJ", "sd_E_mJ", "misfire_rate"])
            for di, d in enumerate(dwells):
                for vi, v in enumerate(volts):
                    w.writerow([v, d, n, mean_E[di][vi], sd_E[di][vi], rate[di][vi]])

    # ---- exports (all return bytes so the dashboard can offer them as downloads)
    def csv_bytes(self):
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=FIELDS)
        w.writeheader()
        for r in self.rows:
            w.writerow({k: r.get(k) for k in FIELDS})
        return buf.getvalue().encode()

    def _zip(self, files):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for arcname, path in files:
                z.write(path, arcname)
        return buf.getvalue()

    def waveforms_zip_bytes(self):
        files = [(f"waveforms/{p.name}", p) for p in self.waves.values()]
        if self.last_wave is not None:
            last = self.dir / "last_shot_waveform.npz"
            np.savez_compressed(last, dt=self.last_wave["dt"], i_coil=self.last_wave["i_coil"], i_spark=self.last_wave["i_spark"])
            files.append(("last_shot_waveform.npz", last))
        readme = self.dir / "waveforms_README.txt"
        readme.write_text("Each .npz file holds: dt (seconds per sample), i_coil (A), i_spark (A).\n"
                          "Python:  d = numpy.load('shot_00001.npz');  t = numpy.arange(len(d['i_coil'])) * d['dt']\n")
        files.append(("README.txt", readme))
        return self._zip(files)

    def pngs_zip_bytes(self):
        from . import report
        paths = report.render_pngs(self, self.dir / "plots")
        return self._zip([(p.name, p) for p in paths])

    def pdf_bytes(self):
        from . import report
        path = self.dir / "report.pdf"
        report.render_pdf(self, path)
        return path.read_bytes()

    def bundle_bytes(self):
        from . import report
        pngs = report.render_pngs(self, self.dir / "plots")
        pdf = self.dir / "report.pdf"
        report.render_pdf(self, pdf)
        try:
            self._csv.flush()
        except Exception:
            pass
        files = [("shots.csv", self.dir / "shots.csv"), ("settings.json", self.dir / "settings.json"), ("report.pdf", pdf)]
        if (self.dir / "sweep.csv").exists():
            files.append(("sweep.csv", self.dir / "sweep.csv"))
        files += [(f"plots/{p.name}", p) for p in pngs]
        files += [(f"waveforms/{p.name}", p) for p in self.waves.values()]
        return self._zip(files)

    def close(self):
        try:
            self._csv.close()
        except Exception:
            pass
