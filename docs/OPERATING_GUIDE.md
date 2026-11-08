# Operating guide — how to run this whole project

This is the step-by-step manual for actually **using** the spark ignitor test bench:
software setup, the dashboard, the hardware bring-up order, a normal test session from
start to finish, what to do when something trips, and where everything lives. It assumes
no programming or electronics background. Technical background (why things are designed
this way) is in `docs/PROJECT_CONTEXT.md`; wiring detail is in `docs/HARDWARE.md`;
instructions for an AI assistant working on the code are in `CLAUDE.md`. This guide ties
them together into "what do I actually do, in order."

**Read the safety rules (section 7) before the first time you connect anything to the coil.**

---

## 1. One-time computer setup

Do this once per computer.

1. Install Python 3.10 or newer from [python.org](https://www.python.org/) (Windows
   build). When the installer asks, tick **"Add Python to PATH"**.
2. Get this project folder onto the computer (copy it, or `git clone` the repository).
3. Open a terminal **in this folder** (in Windows Explorer: Shift + right-click inside
   the folder → "Open PowerShell window here" or "Open terminal here").
4. Run these four lines one at a time:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   python -m spark_ignitor selftest
   ```
   A **venv** is a private copy of Python's packages just for this project, so it does not
   clash with anything else on the computer. You should see `ALL TESTS PASSED` at the end.
   If you close the terminal and come back later, run `.venv\Scripts\activate` again
   before any `python -m spark_ignitor ...` command — that line "turns on" the venv for
   that terminal window.

If `ALL TESTS PASSED` did not print, stop here and fix that first — nothing past this
point will work reliably otherwise.

---

## 2. Try it in simulation first (always, every time something changes)

**Simulation mode** means the program pretends to be the Arduino, the Rigol power supply
and the PicoScope. No hardware is touched. This is the safe place to learn the dashboard
and to check a software change before it goes near real voltage.

1. Start it: double-click `START_DASHBOARD.bat`, or run `python -m spark_ignitor dashboard`
   in the terminal.
2. Open the address it prints, normally **http://localhost:8080**, in a web browser.
   - If you see an error like "only one usage of each socket address" / "port already in
     use", something else on the computer is already using port 8080. Run
     `python -m spark_ignitor dashboard --port 8090` instead and open
     `http://localhost:8090`.
3. On the page: press **Connect**. The three badges (Rigol / Arduino / Scope) should turn
   from grey to a colour, and the orange **SIMULATION** badge stays on — that badge is
   your reminder that nothing real is attached.
4. Press **Fire once**. A waveform and numbers should appear.
5. Press **Run batch** (default 20 shots) and watch the **Shots** tab fill in.
6. Open the **Sweep** tab, press **Start sweep**, and check the two colour maps draw.
7. Open the **Export** tab and try each button once (CSV, waveforms, PNG, PDF, everything)
   — files should download.
8. Press **STOP** (top-right, red) at least once, just to see what it does: it ends
   whatever is running and turns everything off.

If all of that works, the software side is healthy. Anything below this line involves
real electricity — slow down.

---

## 3. What each part of the dashboard means

- **Header badges:** Rigol / Arduino / Scope show grey (not connected), or a colour once
  connected. **SIMULATION** (orange) means no real device is in the loop for whichever
  parts are still set to "sim". **not armed / ARMED** shows whether the coil driver is
  currently live. **no trip / TRIP: ...** shows the safety state (see section 6).
- **STOP** (red button, top-right): always available. Ends the current run, disarms the
  Arduino, and switches the Rigol output off. This is your software panic button —
  press it any time something looks wrong, then look at the hardware panic button next
  (the e-stop), not instead of it.
- **Controls card (left):**
  - **Connect / Disconnect** — opens or closes the link to whichever devices are set to
    "real" in the **Devices** expansion panel below (Arduino, Rigol, Scope each have
    their own sim/real switch, plus the Arduino COM port and the Rigol's VISA resource
    name).
  - **Supply voltage (V)** and **Dwell (µs)** — the two numbers you set before firing.
    **Dwell** is how long the coil is told to charge before the spark fires; longer dwell
    stores more energy but heats the coil more. The slider under each box is capped to the
    safe limits from `config.json`.
  - **Fire once** — one shot at the current voltage/dwell.
  - **Run batch** — fires the "Shots in a batch" number of shots at the same
    voltage/dwell, with a rest between each (coil cooling).
  - **Auto-fire** — keeps firing at the current settings until you press STOP or it trips.
    Only use this once single shots and batches already look right.
  - **Reset trip** — clears a trip so you can run again, after you have understood and
    fixed why it tripped (see section 6). It does not re-arm anything by itself.
- **Live numbers:** I peak (A), stored energy (mJ), L estimate (mH), burn time (ms), shot
  count, misfire rate — computed from the last shot / batch, explained in section 8.
- **Live graph:** coil current and spark current against time, for the most recent shot.
- **Tabs below:**
  - **Shots** — a table of every shot this session plus a chart of stored energy per shot
    (red dots = misfires).
  - **Sweep** — type a comma-separated list of voltages and dwell times and a number of
    shots per combination; it fires every combination (in random order by default, so
    coil heating does not bias one setting over another) and draws two heat maps.
  - **Export** — download the shot table (CSV, opens in Excel), the raw waveforms (ZIP of
    `.npz` files), the graph pictures (ZIP of PNGs), a PDF report, or everything together.
    Every run is also saved automatically on disk under `data/<timestamp>/` even if you
    never press a button here.
  - **Log** — a plain-text log of what the program did and any errors.

---

## 4. Moving to real hardware — do this in order, do not skip steps

Each step below only adds **one** real device. Keep everything else in simulation until
the step for it. **Do not connect the coil until step 5 has been done safely with
step 4's checks passed.**

### Step A — Arduino only
1. Open `firmware/spark_trigger/spark_trigger.ino` in the Arduino IDE and upload it to
   the Arduino Uno. (The Arduino is the small board that sends the trigger pulse; the
   firmware is the program that runs on it — you only upload it once, or again if it
   changes.)
2. Run `python -m spark_ignitor ports` to find its COM port (for example `COM3`).
3. In the dashboard's **Devices** panel, set Arduino to "real" and type that port in.
   Leave Rigol and Scope on "sim".
4. Connect. The Arduino badge should turn from grey. Try **Fire once** with nothing
   wired to the Arduino's output yet except, later, an LED + 330 ohm resistor on the
   trigger line, as in `docs/HARDWARE.md` — you should see it blink.
5. If the Arduino goes silent for 3 seconds it prints `WDG SAFE` and disarms itself — this
   is the firmware's own watchdog, a safety feature, not a bug.

### Step B — add the Rigol power supply
1. With **nothing connected to the Rigol's output** yet, find its name with
   `python -m spark_ignitor ports` (it lists VISA instruments too).
2. Set Rigol to "real" with that resource name; Scope stays "sim".
3. Connect, then try a very small voltage/dwell. Check on the Rigol's own front panel that
   the voltage and current limit match what the dashboard asked for, and that OVP (over-
   voltage protection) is set — this program sets it from `ovp_V` in `config.json`
   (default 14 V; the supply's own default of 33 V would protect nothing in this 12 V
   circuit).
4. **Exact OVP command syntax has not been confirmed on a real Rigol yet** — if this step
   errors, read the message (the program checks `:SYST:ERR?` after every command) and
   check the Rigol DP800 Programming Guide, chapter 2, for the right syntax, with an
   experienced team member if possible.

### Step C — add the PicoScope
1. Close PicoScope 7 (the manufacturer's own app) — only one program can use the scope at
   a time.
2. Install the PicoSDK matching your Python's bit-width (32- or 64-bit — they must match).
3. Run `python -m spark_ignitor scope-check`. It tells you the series (only `ps2000a` and
   `ps3000a` are supported here; if yours is a 4000A/5000A series, the code needs
   extending first — ask for help rather than guessing).
4. Set `scope_mode` in `config.json` (or in the Devices panel) to that series.
5. Run `python -m spark_ignitor scope-test` — this captures one block **without** firing
   anything, just to prove the scope settings work.
6. In the dashboard, connect with Scope real and Arduino/Rigol still "sim" first, so you
   can see a waveform appear with no voltage anywhere near the coil.

### Step D — measured values, not estimates
Before anything fires for real: measure the coil's actual inductance and resistance
(LCR meter, or fit the ramp from a first low-voltage shot), the current clamp's V/A scale
(check the switch on the clamp), and the shunt resistor value. Put the measured numbers
into `config.json` (`L_mH`, `R_ohm`, `clamp_V_per_A`, `shunt_ohm`) — the simulation
numbers (3 mH, 0.5 ohm) are the team's estimate, not a measurement, and the live energy
and inductance numbers on the dashboard are only as good as these values.

### Step E — the coil, supervised, low voltage first
Only now connect the coil (and, later, the spark plug). Someone who knows the rig must be
in the room. Start at the lowest sensible voltage and dwell, with the enclosure closed and
the e-stop tested. Increase gradually. See `docs/HARDWARE.md` for the exact wiring order
and the "before power" continuity checks — do those checks again if any wiring changed.

---

## 5. A normal test session, start to finish

Use this checklist every time, once hardware is involved (skip the hardware lines in
simulation-only sessions).

**Before power:**
- [ ] Enclosure closed, discharge stick within reach, e-stop tested (press it, confirm
      the relay drops power).
- [ ] A person who knows the rig is present — never run supervised-only steps alone.
- [ ] `config.json` reviewed: is `ovp_V`, `I_trip_A`, `max_dwell_us`, `max_voltage_V`
      still what you expect? Has anyone raised `max_dwell_us` past 5000? (It must match
      the firmware limit — do not raise either without an explicit, informed decision.)
- [ ] Venv active (`.venv\Scripts\activate`), selftest still passes after any code change.

**Starting up:**
- [ ] Start the dashboard, open it in the browser.
- [ ] Connect. Check all three badges and that **TRIP** shows green "no trip".
- [ ] Fire one shot at a low, known-safe voltage/dwell before anything bigger.

**During the session:**
- [ ] Watch the live graph and numbers after every shot, not just at the end of a batch.
- [ ] If anything looks wrong — smell, sound, a number far outside what you expect —
      press **STOP**, then the physical e-stop if needed. Investigate before continuing.
- [ ] Use **Run batch** for a fixed small set, **Sweep** for a planned grid of points,
      **Auto-fire** only once you trust the settings, for short periods, watching it.
- [ ] Note anything unusual in the **Log** tab or on paper — timestamps help later.

**Ending the session:**
- [ ] Press **Disconnect** (this is on top of what a run already does automatically —
      every run already disarms the Arduino and switches the Rigol output off when it
      ends, stops, or trips).
- [ ] Physically confirm the Rigol output is off and discharge the big capacitor with the
      discharge stick before touching any wire.
- [ ] Export what you need from the **Export** tab (it is also already saved under
      `data/<timestamp>/` automatically).
- [ ] Write down, in your own notes, what changed since the last session (new config
      values, new wiring, anything that tripped and why).

---

## 6. When something trips

A **trip** means the software noticed something unsafe and stopped the run on its own —
disarming the Arduino and switching the Rigol output off. This is working as intended. The
dashboard shows the reason next to **TRIP** and in the **Log** tab. The trips are:

| Trip reason | What it means | What to check |
|---|---|---|
| Peak current above `I_trip_A` | The coil current went higher than the configured limit | Is the voltage/dwell too high? Is `L_mH`/`R_ohm` in config still the team's estimate, not measured? |
| Rigol voltage differs from the setpoint | The supply's own readback does not match what was asked for | Loose connection, wrong channel, or the supply is current-limiting |
| Dwell or voltage above the configured limits | The dashboard tried to ask for more than `max_dwell_us` / `max_voltage_V` | Check what you typed; these limits should not be raised without an explicit decision |
| N misfires in a row (`misfires_to_trip`) | The coil is not producing a spark | Loose trigger wiring, dwell too short, voltage too low, or the plug/shunt circuit is open |
| Arduino watchdog or heartbeat failure | The Arduino went silent (its own 3-second watchdog disarms it) or stopped answering `?` | USB cable, driver (CH340), or a crashed sketch — re-upload the firmware |
| Any device exception | pyserial / pyvisa / picosdk raised an error | Read the exact message in the Log tab; usually a cable, driver, or "already in use by another program" issue |

After a trip: **understand the reason before pressing Reset trip.** Resetting does not
change anything about the circuit — it only clears the flag so you can try again.

---

## 7. Safety rules (do not weaken these without an explicit, informed decision)

- The coil makes tens of kV; later stages store energy in a capacitor. Software is the
  **second** line of defence. The first line is hardware: fuse, e-stop, enclosure,
  discharge stick.
- A person who knows the rig must be present for every first test at a new setting.
- Every run arms the coil itself and, when it ends, stops, or trips, disarms the Arduino
  and switches the Rigol output off.
- `max_dwell_us` is 5000 in `config.json` **and** in the firmware. Both must agree.
- The Rigol's own over-voltage trip must be set from `ovp_V`, never left at the supply's
  own default (33 V protects nothing in a 12 V circuit).
- Never connect the PicoScope to the high-voltage side. Probes go on the current clamp and
  across the shunt only.
- Never add anything that fires the coil automatically on start-up, on a timer, or from a
  remote/read-only viewer.
- Never touch the rig with power on. Always discharge the big capacitor before moving a
  wire.

---

## 8. Glossary (plain-language, for a beginner)

- **Dwell** — how long the coil driver holds the trigger line high before letting the coil
  fire; longer dwell = more stored energy, but more heat.
- **Arm / armed** — the coil driver is live and will fire on the next trigger. The
  dashboard arms only for the duration of a run and disarms itself afterwards.
- **Trip** — the software stopped a run because a safety check failed (section 6).
- **Misfire** — a shot where no spark current was detected on the shunt.
- **Optocoupler** — a small chip that passes the trigger signal through light, not a wire,
  so the Arduino's electronics stay electrically separate from the coil's.
- **Shunt** — a precise, non-inductive resistor the spark current is measured across
  (voltage = current × resistance).
- **Current clamp** — a sensor that clips around a wire and reports the current in it
  without needing to cut into the wire.
- **OVP / OCP** — over-voltage / over-current protection, a trip built into the power
  supply itself, separate from this program's own trips.
- **VISA resource** — the address the Rigol power supply is identified by over USB (looks
  like `USB0::0x1AB1::0x0E11::...::INSTR`); find it with `python -m spark_ignitor ports`.
- **Sim / real** — whether a device is a software stand-in (sim) or the physical unit
  (real); each device (Arduino, Rigol, Scope) is switched independently.
- **venv** — a private, per-project copy of the Python packages this program needs.

---

## 9. Where things live

```
spark_ignitor/     the program itself (config, arduino, rigol, scope, analysis, safety, storage, report, rig, app, cli)
firmware/          the Arduino sketch you upload once
tests/             automated dashboard tests (pytest) — run after any code change
config.json        your settings — created by `python -m spark_ignitor init-config`
data/              every run's own folder: shots.csv, settings.json, waveforms, reports
docs/HARDWARE.md          wiring, breadboard holes, part notes
docs/PROJECT_CONTEXT.md   why things were designed this way, open questions, team history
docs/assets/              schematics, breadboard photos, parts lists, example report
CLAUDE.md                 instructions for an AI assistant working on this code
README.md                 short version of install + hardware bring-up
docs/OPERATING_GUIDE.md   this file
```

### Commands reference
```
python -m spark_ignitor selftest             7 hardware-free checks; must print ALL TESTS PASSED
python -m pytest -q                          4 dashboard tests with a simulated browser
python -W error -m spark_ignitor selftest    same selftest, also catches numeric warnings
python -m spark_ignitor dashboard            starts the web page (add --port 8090 if 8080 is busy)
python -m spark_ignitor init-config          writes a default config.json to edit
python -m spark_ignitor ports                lists serial ports and VISA instruments
python -m spark_ignitor scope-check          tells you which PicoScope series is connected
python -m spark_ignitor scope-test           one block capture from the real scope, no trigger
```

---

## 10. Periodic maintenance / before a progress meeting

- Re-run `python -m spark_ignitor selftest` and `python -m pytest -q` after any code
  change, before trusting the dashboard again.
- Re-check continuity (section "before power" in `docs/HARDWARE.md`) after any rewiring.
- Keep a running note of what was measured vs. still estimated (coil L/R, clamp scale,
  shunt value) — update `config.json` as real measurements come in, and note the date.
- Before a professor meeting: export a PDF report and the shot table from a recent
  session (Export tab), and check `docs/PROJECT_CONTEXT.md` section 5 (open questions) for
  anything that should be raised.
