# App guide — using the dashboard and understanding its data logging

This is the detailed reference for the dashboard itself: every control, what it does, and
— in depth — exactly what gets saved, where, in what format, and how to open it later. For
the bigger picture (one-time computer setup, connecting real hardware, safety rules, a
session checklist) see `docs/OPERATING_GUIDE.md` first. This file assumes the dashboard is
already running (`python -m spark_ignitor dashboard`) and you have it open in a browser.

---

## 1. The dashboard, control by control

### Header bar
| Control | Meaning |
|---|---|
| **Rigol / Arduino / Scope badges** | Grey = not connected. Coloured = connected. One badge per device, because each can be real or simulated independently. |
| **SIMULATION** (orange badge) | Shown whenever at least the devices still set to "sim" are standing in for hardware. If all three are real, this badge does not appear. |
| **not armed / ARMED** | Whether the coil driver is currently live. It is only armed for the moment a shot fires. |
| **no trip / TRIP: ...** | The safety state. See `docs/OPERATING_GUIDE.md` section 6 for what each trip reason means. |
| **STOP** (red) | Ends whatever is running right now: a batch, a sweep, or auto-fire. Also disarms the Arduino and switches the Rigol output off. Always available, always safe to press. |

### Controls card
| Control | Meaning |
|---|---|
| **Connect** | Opens the link to every device (real ones per the Devices panel, sim ones in software) and **starts a new data folder** for this session — see section 2. |
| **Disconnect** | Closes the devices and **closes the current data folder**. Nothing more can be logged into it after this. |
| **Supply voltage (V)** | The voltage requested for the next shot/batch/auto-fire. Capped by `max_voltage_V` in `config.json`. |
| **Dwell (µs)** | How long the coil charges before it fires. Capped by `max_dwell_us` (5000 by default, matching the firmware's own limit). |
| **Shots in a batch** | How many shots **Run batch** fires in one go, all at the current voltage/dwell. |
| **Fire once** | One shot, convenience shortcut for "Run batch" with count 1. |
| **Run batch** | Fires the batch size above, with a rest between shots (`min_rest_s` in config) so the coil can cool. |
| **Auto-fire** | Keeps firing at the current voltage/dwell until you press STOP or a trip happens. Use only once you trust a setting — it has no built-in shot limit. |
| **Reset trip** | Clears a trip flag so you can run again. Does not undo whatever caused the trip — understand the reason first (section 6 of the operating guide). |
| **Devices (expansion panel)** | Per-device sim/real switch, the Arduino COM port, and the Rigol VISA resource string. Changing these only takes effect on the next **Connect**. |

### Live view
- **Metric tiles** — I peak (A), stored energy (mJ), L estimate (mH), burn time (ms), shot
  count, misfire rate. These always describe the **most recent shot or batch**, not a
  running session average (for a session average, see the Shots tab or the PDF report).
- **Waveform graph** — coil current and spark current for the **most recent single shot**,
  against time in milliseconds.

### Tabs
- **Shots** — a live table of every shot fired since Connect, plus a chart of stored
  energy per shot (misfires shown as red dots). This table is the on-screen view of the
  same data being written to `shots.csv` on disk (section 3).
- **Sweep** — type comma-separated voltages and dwell times and a shot count per
  combination; fires every combination (random order by default) and draws two colour
  maps (mean energy, misfire rate). Writing `8, 10, 12` and `1000, 2000, 3000` with 5
  shots per point fires 3 × 3 × 5 = 45 shots total.
- **Export** — on-demand downloads built from everything logged so far this session (CSV,
  waveforms ZIP, PNG ZIP, PDF report, or all of it bundled). See section 4 — this tab does
  **not** control whether data is being saved; saving already happened automatically.
- **Log** — a plain-text log of connects, disconnects, every trip, and device errors.
  Check this first whenever something unexpected happens.

---

## 2. When logging starts and stops (read this before your first real session)

**A new data folder is created the moment you press Connect**, and it is the *only* place
every shot from then on is written to, until you press Disconnect. This means:

- Firing shots, running batches, running sweeps, and auto-fire **all log into the same
  folder** for as long as you stay connected — they do not start new folders of their own.
- **Disconnect closes that folder.** If you Connect again (even seconds later), a brand
  new, separate folder starts, with its own `shots.csv` starting back at shot 1.
- There is no "pause" — only connected (logging) or disconnected (not logging).
- If the program crashes or the computer loses power mid-session, `shots.csv` is safe up
  to the last completed shot (it is flushed to disk after every single shot, not just at
  the end), but nothing after that point is saved.

**Practical upshot:** decide your session boundaries by when you Connect/Disconnect, not
by which button you press for firing. If you want "today's sweep" and "today's batches" in
separate folders, Disconnect and Connect again between them.

---

## 3. What gets saved automatically, and where

Every run (one Connect-to-Disconnect session) gets its own folder:

```
data/Run_20270304_143210/
├── settings.json              full config snapshot at the moment you connected
├── shots.csv                  one row per shot, updated live (see table below)
├── sweep.csv                  only if you ran a sweep this session
└── waveforms/
    └── shot_00001.npz         raw waveform of every Nth shot (see "waveform_every")
```

The folder name is a timestamp (`Run_YYYYMMDD_HHMMSS`), so folders sort chronologically
and never collide. `data_dir` in `config.json` controls where the `data/` folder itself
lives (default: `data` next to the program, i.e. a relative path from wherever you started
the dashboard from).

### `settings.json`
A full dump of every field in `config.json` **as it was at the moment you connected** —
L_mH, R_ohm, all the trip limits, device modes, everything. This is what lets you look
back at an old run and know exactly what the program believed about the coil and the
safety limits at the time, even if `config.json` has since been edited.

### `shots.csv` — one row per shot
| Column | Meaning | Unit |
|---|---|---|
| `shot` | Shot number within this session (1, 2, 3, ...) | — |
| `time` | When the shot was fired | timestamp |
| `batch` | Which batch/sweep-point/auto-fire run this shot belongs to | — |
| `vset_V` | Supply voltage that was requested | V |
| `vread_V` | Voltage the Rigol actually reported back | V |
| `dwell_us` | Dwell time that was requested | µs |
| `ipk_A` | Peak coil current — the mean of the 5 highest current samples in the waveform (this avoids one noisy sample looking like the peak) | A |
| `E_mJ` | Stored energy, computed as ½ × L × I_peak² using the `L_mH` in `config.json` | mJ |
| `L_est_mH` | Inductance estimated from the slope of the current ramp (5–20 % of peak, line-fit on smoothed data); `NaN`/blank if the ramp was too short or noisy to fit | mH |
| `burn_ms` | How long the spark current stayed above `spark_threshold_A` | ms |
| `ispark_max_mA` | Peak spark current measured across the shunt | mA |
| `misfire` | `True` if no spark was detected (burn time 0 or peak spark current below threshold) | — |

This file is what you open in Excel for your own analysis or to paste into a lab notebook
or a report. It updates after every single shot — you can open it in Excel *while the
dashboard is still running* to see live progress (Excel will ask to reload if you re-open
it, since the program keeps writing to it).

### `sweep.csv` — one row per (voltage, dwell) combination
Only created if you ran a sweep. Columns: `vset_V`, `dwell_us`, `shots` (how many fired at
that point), `mean_E_mJ`, `sd_E_mJ` (standard deviation), `misfire_rate`. This is the
numeric table behind the two colour maps on the Sweep tab.

### `waveforms/shot_NNNNN.npz` — the raw scope traces
Saving every shot's full waveform would use a lot of disk space, so only every **Nth**
shot is saved raw, where N = `waveform_every` in `config.json` (default 10 — shots 1, 11,
21, ... in a given session). The metrics in `shots.csv` (peak current, energy, etc.) are
still computed for **every** shot; only the raw trace is thinned out. Lower
`waveform_every` to 1 if you need every single raw waveform (uses more disk space and disk
I/O — fine for careful low-shot-count work, worth avoiding during a long auto-fire run).

Each `.npz` file holds three arrays:
- `dt` — seconds per sample (so you can rebuild the time axis)
- `i_coil` — coil current in amps, one value per sample
- `i_spark` — spark current in amps, one value per sample

To open one in Python:
```python
import numpy as np
d = np.load("shot_00001.npz")
t = np.arange(len(d["i_coil"])) * d["dt"]        # time axis in seconds
i_coil = d["i_coil"]                              # amps
i_spark = d["i_spark"]                            # amps
```
(A copy of this snippet is also written as `waveforms_README.txt` whenever you download
the waveforms ZIP from the Export tab.)

---

## 4. The Export tab — downloads, on demand

Everything in section 3 is already saved to disk automatically. The **Export** tab exists
for getting a copy out of the browser (to email, to put on a USB stick, to attach to a
report) without having to go find the `data/` folder on disk yourself.

| Button | What you get |
|---|---|
| **Shot table (CSV, opens in Excel)** | A copy of `shots.csv` as it stands right now. |
| **Raw waveforms (ZIP)** | Every saved `.npz` so far, plus the very latest shot's waveform even if it wasn't one of the "every Nth" ones, plus the README snippet above. |
| **Graph pictures (PNG, ZIP)** | Re-rendered PNGs: last shot's waveform, energy-vs-shot, an energy histogram, and (if you ran a sweep) the two sweep colour maps. |
| **PDF report** | A multi-page PDF — see section 5. |
| **Everything (ZIP)** | `shots.csv` + `settings.json` + `sweep.csv` (if present) + the PNGs + the PDF + all saved waveforms, in one file. This is the one to grab before a progress meeting. |

A few things worth knowing:
- Pressing an Export button **re-renders** the PNGs and PDF from the data gathered so far
  — they are not stale copies from an earlier point in the session, they are generated
  fresh each time you click.
- Exporting does **not** stop or affect logging — you can export mid-batch.
- If you have fired zero shots since connecting, the Export buttons will warn "No shots
  recorded yet" instead of producing an empty file.
- Exporting from the browser is a convenience copy; the authoritative, permanent record is
  always the `data/Run_.../` folder on disk, which was already written continuously.

---

## 5. What's in the PDF report

The PDF (`report.pdf`, or via the Export tab) has up to four pages, built from whatever
has been logged so far this session:

1. **Summary page** — when it was created, the data folder name, a clear red warning if
   this is simulated data, the headline numbers (shot count, misfire count and rate, mean
   stored energy and its standard deviation, mean peak current, mean burn time), and the
   **full settings dump** (every `config.json` field at connect time) in monospace text.
2. **Plots page** — the last shot's waveform, stored energy per shot, and an energy
   histogram.
3. **Results-by-setting table** — if shots were fired at more than one combination of
   voltage/dwell, a table with one row per combination: shot count, mean/SD energy,
   misfire rate, mean peak current. Capped at 45 rows.
4. **Sweep maps page** — only if a sweep was run this session: the two colour maps (mean
   energy, misfire rate) as full-page plots.

This PDF is meant to be handed to someone else (a professor, a teammate) without them
needing to open the dashboard at all — it is self-contained.

---

## 6. Practical tips for logging a real session well

- **Decide your Connect/Disconnect boundaries up front.** If you plan to do three
  distinct things in a lab visit (e.g. a shake-down batch, a planned sweep, then
  free-form auto-fire testing), consider Disconnecting and reconnecting between them so
  each gets a clean, separately-named folder — easier to find again later than one giant
  mixed folder.
- **Lower `waveform_every` to 1** for short, important batches where you want every raw
  trace (e.g. calibration shots to measure L and R); leave it at 10 or higher for long
  exploratory sweeps or auto-fire runs, to save disk space.
- **Measured vs. estimated values matter for every number in `shots.csv`.** `E_mJ` is
  computed from `L_mH` in `config.json` — if that is still the team's 3 mH estimate
  rather than your coil's measured value, every energy number in every exported file
  inherits that same uncertainty. Update `config.json` as soon as you have a measured
  value, and note the date you did it (section 10 of the operating guide).
- **Back up the `data/` folder off the lab laptop** regularly — it is not tracked in git
  (see `.gitignore`) and nothing else backs it up automatically.
- **Don't edit files inside an open session's folder while connected.** `shots.csv` is
  held open by the program for writing; editing it externally mid-session can conflict
  with the program's own writes. Wait until you Disconnect, or work from an exported copy.
- **The Export tab's PDF/PNGs are regenerated, not accumulated** — if you want a record of
  "what the report looked like halfway through," export it then and keep that copy; a
  later export from the same still-open session will reflect everything fired by then.

---

## 7. Quick reference: all the files you'll ever see in a run folder

| File | Created when | Rows added |
|---|---|---|
| `settings.json` | Connect | once, never updated again this session |
| `shots.csv` | Connect (header only) | one row per shot, as it fires |
| `sweep.csv` | After a sweep finishes | one row per (voltage, dwell) point |
| `waveforms/shot_NNNNN.npz` | Every Nth shot (`waveform_every`) | one file per saved shot |
| `last_shot_waveform.npz` | Only inside a downloaded waveforms ZIP | the most recent shot, always included |
| `waveforms_README.txt` | Only inside a downloaded waveforms ZIP | — |
| `plots/*.png` | Only inside a downloaded PNG ZIP or bundle | re-rendered each export |
| `report.pdf` | Only inside a downloaded PDF or bundle | re-rendered each export |
