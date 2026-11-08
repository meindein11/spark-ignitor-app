import numpy as np


def compute_metrics(i_coil, i_spark, dt, vset, cfg):
    """Turn the two waveforms into the numbers that are logged for every shot."""
    i_coil = np.asarray(i_coil, float)
    i_spark = np.asarray(i_spark, float)
    ipk = float(np.mean(np.sort(i_coil)[-5:]))                 # mean of the 5 highest samples (noise-proof)
    energy_mJ = 0.5 * cfg.L_mH * ipk ** 2                      # 1/2 L I^2, with L in mH the result is mJ
    # L estimate: straight-line fit of the first part of the ramp (5 % to 20 % of the peak).
    # The signal is smoothed first, so baseline noise cannot be mistaken for the start of the ramp.
    l_est = float("nan")
    if ipk > 0.5:
        sm = np.convolve(i_coil, np.ones(25) / 25, mode="same")
        lo, hi = 0.05 * ipk, 0.20 * ipk
        above_lo = np.where(sm >= lo)[0]
        if above_lo.size:
            i0 = int(above_lo[0])
            above_hi = np.where(sm[i0:] >= hi)[0]
            if above_hi.size and above_hi[0] >= 10:
                idx = np.arange(i0, i0 + int(above_hi[0]))
                t = (idx - idx[0]) * dt                        # time axis starts at zero (well conditioned)
                try:
                    slope = float(np.polyfit(t, i_coil[idx], 1)[0])     # A per second
                except (np.linalg.LinAlgError, ValueError):
                    slope = 0.0
                if slope > 0:
                    l_est = vset / slope * 1e3                 # H -> mH
    above = i_spark > cfg.spark_threshold_A
    burn_ms = float(above.sum() * dt * 1e3)
    ispark_max_mA = float(i_spark.max() * 1e3)
    misfire = bool(burn_ms == 0.0 or i_spark.max() < cfg.spark_threshold_A)
    return dict(ipk_A=ipk, E_mJ=energy_mJ, L_est_mH=l_est, burn_ms=burn_ms,
                ispark_max_mA=ispark_max_mA, misfire=misfire)


def stats_batch(rows):
    """Average and spread of a list of shot rows. Energy is averaged over the shots that sparked."""
    n = len(rows)
    if n == 0:
        return dict(n=0)
    ok = [r for r in rows if not r["misfire"]]
    e = np.array([r["E_mJ"] for r in ok]) if ok else np.array([])
    return dict(n=n, misfires=n - len(ok), misfire_rate=(n - len(ok)) / n,
                mean_E=float(e.mean()) if e.size else float("nan"),
                sd_E=float(e.std(ddof=1)) if e.size > 1 else float("nan"),
                mean_ipk=float(np.mean([r["ipk_A"] for r in rows])),
                mean_burn=float(np.mean([r["burn_ms"] for r in ok])) if ok else float("nan"))
