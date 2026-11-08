import time
from dataclasses import asdict
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
from .analysis import stats_batch


def _wave_axes(session, axs):
    w, r = session.spark_wave, session.spark_row
    label = "Latest shot that sparked"
    if w is None and session.rows:
        w, r, label = session.last_wave, session.rows[-1], "Last shot (no spark in this run)"
    if w is None:
        for a in axs:
            a.text(0.5, 0.5, "no shots yet", ha="center", va="center", transform=a.transAxes)
        return
    t = np.arange(len(w["i_coil"])) * w["dt"] * 1e3
    axs[0].plot(t, w["i_coil"], color="#1f77b4"); axs[0].set_ylabel("coil current (A)")
    axs[0].set_title(f"{label} (#{r['shot']}): {r['vset_V']:.1f} V, {r['dwell_us']:.0f} us, "
                     f"I peak {r['ipk_A']:.1f} A, E {r['E_mJ']:.0f} mJ", fontsize=10)
    axs[1].plot(t, w["i_spark"] * 1e3, color="#ff7f0e"); axs[1].set_ylabel("spark current (mA)"); axs[1].set_xlabel("time (ms)")
    for a in axs:
        a.grid(alpha=0.3)


def _energy_axes(session, ax):
    rows = session.rows
    if not rows:
        ax.text(0.5, 0.5, "no shots yet", ha="center", va="center", transform=ax.transAxes); return
    x = [r["shot"] for r in rows]; e = [r["E_mJ"] for r in rows]
    ax.plot(x, e, ".-", color="#555", lw=0.8)
    mis = [r for r in rows if r["misfire"]]
    ax.plot([r["shot"] for r in mis], [r["E_mJ"] for r in mis], "rx", label="misfire")
    ax.set_xlabel("shot number"); ax.set_ylabel("stored energy (mJ)"); ax.grid(alpha=0.3)
    if mis:
        ax.legend()


def _hist_axes(session, ax):
    e = [r["E_mJ"] for r in session.rows if not r["misfire"]]
    if not e:
        ax.text(0.5, 0.5, "no sparks yet", ha="center", va="center", transform=ax.transAxes); return
    ax.hist(e, bins=min(20, max(5, len(e) // 3)), color="#2ca02c", alpha=0.8)
    ax.set_xlabel("stored energy (mJ)"); ax.set_ylabel("shots"); ax.grid(alpha=0.3)


def _sweep_axes(sw, key, ax, title, fmt, cmap):
    z = sw[key]
    im = ax.imshow(z, origin="lower", aspect="auto", cmap=cmap)
    ax.set_xticks(range(len(sw["volts"]))); ax.set_xticklabels([f"{v:g}" for v in sw["volts"]])
    ax.set_yticks(range(len(sw["dwells"]))); ax.set_yticklabels([f"{d:g}" for d in sw["dwells"]])
    ax.set_xlabel("supply voltage (V)" + ("\n(white = every shot misfired, so there is no energy to average)" if key == "mean_E" else "")); ax.set_ylabel("dwell (us)"); ax.set_title(title, fontsize=10)
    for (i, j), val in np.ndenumerate(z):
        if np.isfinite(val):
            ax.text(j, i, fmt(val), ha="center", va="center", fontsize=8, color="white" if im.norm(val) < 0.5 else "black")
    plt.colorbar(im, ax=ax)


def render_pngs(session, outdir):
    outdir = Path(outdir); outdir.mkdir(parents=True, exist_ok=True)
    paths = []
    fig, axs = plt.subplots(2, 1, figsize=(9, 6), sharex=True); _wave_axes(session, axs); fig.tight_layout()
    p = outdir / "last_shot.png"; fig.savefig(p, dpi=150); plt.close(fig); paths.append(p)
    fig, ax = plt.subplots(figsize=(9, 4)); _energy_axes(session, ax); fig.tight_layout()
    p = outdir / "energy_vs_shot.png"; fig.savefig(p, dpi=150); plt.close(fig); paths.append(p)
    fig, ax = plt.subplots(figsize=(6, 4)); _hist_axes(session, ax); fig.tight_layout()
    p = outdir / "energy_histogram.png"; fig.savefig(p, dpi=150); plt.close(fig); paths.append(p)
    if session.sweep:
        fig, ax = plt.subplots(figsize=(7, 5)); _sweep_axes(session.sweep, "mean_E", ax, "Mean stored energy (mJ)", lambda v: f"{v:.0f}", "viridis"); fig.tight_layout()
        p = outdir / "sweep_energy.png"; fig.savefig(p, dpi=150); plt.close(fig); paths.append(p)
        fig, ax = plt.subplots(figsize=(7, 5)); _sweep_axes(session.sweep, "rate", ax, "Misfire rate", lambda v: f"{100*v:.0f}%", "Reds"); fig.tight_layout()
        p = outdir / "sweep_misfire_rate.png"; fig.savefig(p, dpi=150); plt.close(fig); paths.append(p)
    return paths


def _groups(rows):
    g = {}
    for r in rows:
        g.setdefault((round(r["vset_V"], 2), round(r["dwell_us"])), []).append(r)
    return g


def render_pdf(session, path):
    cfg = session.cfg
    rows = session.rows
    with PdfPages(path) as pdf:
        # page 1: summary
        fig = plt.figure(figsize=(8.27, 11.69)); fig.text(0.07, 0.95, "Spark ignitor: run report", fontsize=20, weight="bold", color="#1f4e79")
        fig.text(0.07, 0.92, f"Created {time.strftime('%Y-%m-%d %H:%M')}   folder: {session.dir.name}", fontsize=9, color="#555")
        if cfg.all_sim:
            fig.text(0.07, 0.895, "SIMULATED DATA: no real hardware was used for this run.", fontsize=11, color="#c00000", weight="bold")
        s = stats_batch(rows)
        lines = ["RESULTS (all shots in this run)"]
        if s["n"]:
            lines += [f"  shots: {s['n']}     misfires: {s['misfires']}  (rate {100*s['misfire_rate']:.1f} %)",
                      f"  mean stored energy: {s['mean_E']:.1f} mJ     standard deviation: {s['sd_E']:.1f} mJ",
                      f"  mean peak current: {s['mean_ipk']:.2f} A     mean burn time: {s['mean_burn']:.2f} ms"]
        else:
            lines.append("  no shots recorded")
        lines += ["", "SETTINGS"] + [f"  {k}: {v}" for k, v in asdict(cfg).items() if k not in ("data_dir",)]
        fig.text(0.07, 0.86, "\n".join(lines), fontsize=8.5, va="top", family="monospace")
        pdf.savefig(fig); plt.close(fig)
        # page 2: plots
        fig = plt.figure(figsize=(8.27, 11.69)); gs = fig.add_gridspec(4, 2, hspace=0.55, wspace=0.3)
        a1 = fig.add_subplot(gs[0, :]); a2 = fig.add_subplot(gs[1, :], sharex=a1); _wave_axes(session, [a1, a2])
        _energy_axes(session, fig.add_subplot(gs[2, :])); _hist_axes(session, fig.add_subplot(gs[3, 0]))
        pdf.savefig(fig); plt.close(fig)
        # page 3: table by setting
        g = _groups(rows)
        if g:
            fig = plt.figure(figsize=(8.27, 11.69)); ax = fig.add_axes([0.05, 0.05, 0.9, 0.85]); ax.axis("off")
            ax.set_title("Results for each setting", loc="left", weight="bold")
            data = []
            for (v, d), rs in sorted(g.items(), key=lambda kv: (kv[0][1], kv[0][0]))[:45]:
                st = stats_batch(rs)
                data.append([f"{v:g}", f"{d:g}", st["n"], f"{st['mean_E']:.1f}", f"{st['sd_E']:.1f}", f"{100*st['misfire_rate']:.0f} %", f"{st['mean_ipk']:.2f}"])
            tb = ax.table(cellText=data, colLabels=["V (V)", "dwell (us)", "shots", "mean E (mJ)", "SD E (mJ)", "misfires", "mean I peak (A)"], loc="upper center")
            tb.auto_set_font_size(False); tb.set_fontsize(8); tb.scale(1, 1.25)
            pdf.savefig(fig); plt.close(fig)
        # page 4: sweep maps
        if session.sweep:
            fig, axs = plt.subplots(2, 1, figsize=(8.27, 11.69))
            _sweep_axes(session.sweep, "mean_E", axs[0], "Mean stored energy (mJ)", lambda v: f"{v:.0f}", "viridis")
            _sweep_axes(session.sweep, "rate", axs[1], "Misfire rate", lambda v: f"{100*v:.0f}%", "Reds")
            fig.tight_layout(); pdf.savefig(fig); plt.close(fig)
