# Spark ignitor test bench (student research project)

Read this file first, then `docs/PROJECT_CONTEXT.md` (background, decisions, open questions) and `docs/HARDWARE.md`
(circuit, wiring, parts). Figures and the team's spreadsheets are in `docs/assets/`.

## What this is
A university team is building a **railplug** ignition system. Stage A (a normal spark plug driven by an automotive coil)
is being built first. The user is responsible for **everything between the computer and the spark plug**:
Arduino trigger, Rigol supply control, PicoScope measurement, safety, logging, and a one-page dashboard.
This repository is that software. It runs fully in simulation and has NOT yet run on the real hardware.

## About the user (adapt your answers to this)
- Master's student, **beginner** in electronics and in programming tools. Part of a team with a professor who holds progress meetings.
- Wants plain-language, step-by-step explanations, short sentences, and pictures where they help. English only for the UI.
- Likes files they can open: Excel (.xlsx), PDF, PNG. Explain any term the first time (dwell, optocoupler, ...).
- Never assume they know a command. Say where to type it and what they should see. Warn before anything with high voltage.
- Be honest about what is tested and what is not. Do not claim hardware works until it has been run on the bench.

## Hard safety rules (never weaken these without the user's explicit, informed decision)
- High voltage: the coil makes tens of kV; later stages store energy in a capacitor. Software is the SECOND line of defence
  (first: fuse, e-stop, enclosure, discharge stick). A person who knows the rig must be present for first sparks.
- Every run arms the coil itself and, when it ends, stops, or trips, **disarms the Arduino and switches the Rigol output off**.
- `max_dwell_us` is 5000 in config AND in the firmware. Never raise either without being asked and explaining the risk (coil overheating).
- Rigol over-voltage trip must be set from `ovp_V` (the supply's default of 33 V protects nothing in a 12 V circuit).
- Trips: peak current > `I_trip_A`, Rigol readback differs from setpoint, dwell/voltage over limits, N misfires in a row,
  Arduino watchdog or heartbeat failure, any device exception.
- Never connect the PicoScope to the high-voltage side. Probes go on the current clamp and across the shunt only.
- Do not add anything that fires the coil automatically on start-up, on a timer, or from a remote/read-only viewer.

## Commands
```
python -m spark_ignitor selftest        # 7 hardware-free checks; must print ALL TESTS PASSED
python -m pytest -q                     # 4 dashboard tests with NiceGUI's simulated browser
python -W error -m spark_ignitor selftest   # also catches numeric warnings (use before finishing a change)
python -m spark_ignitor dashboard       # http://localhost:8080 (starts in simulation)
python -m spark_ignitor init-config     # writes config.json
python -m spark_ignitor ports           # serial ports and VISA instruments
python -m spark_ignitor scope-check     # which PicoScope series is connected
python -m spark_ignitor scope-test      # one block capture from the real scope (no trigger)
```
Install: `pip install -r requirements.txt` (Python 3.10+, NiceGUI 4.x was used, numpy, matplotlib, pyserial, pyvisa, pyvisa-py, picosdk).

## Architecture (package `spark_ignitor/`)
- `config.py` Config dataclass + JSON. Modes: `arduino_mode` sim|real, `rigol_mode` sim|real, `scope_mode` sim|ps2000a|ps3000a.
- `arduino.py` `Arduino` (pyserial, thread lock, handles unsolicited `WDG SAFE`) and `SimArduino`. Protocol below.
- `rigol.py` `Rigol` (pyvisa, checks `:SYST:ERR?` after every write) and `SimRigol`.
- `scope.py` `SimScope` (coil model), `PicoScope` (picosdk, series by module name), `make_scope`, `check_connected`.
  Scope API: `open()`, `start(vset, dwell_us, auto_trigger_ms)`, `read(timeout)` -> dict(dt, i_coil, i_spark), `close()`.
  Start capture BEFORE firing, read AFTER.
- `analysis.py` `compute_metrics` (I peak = mean of top 5 samples, E = 0.5*L*I^2, L estimate by line fit of the 5-20 % ramp on smoothed data,
  burn time, misfire) and `stats_batch`.
- `safety.py` `Safety.check_setpoint / check_shot`.
- `storage.py` `Session` (one folder per run: shots.csv, settings.json, waveforms/*.npz, sweep.csv; export bytes for CSV, waveforms ZIP, PNG ZIP, PDF, bundle).
- `report.py` matplotlib PNGs and the PDF report.
- `rig.py` `Rig` orchestrator: `connect/disconnect`, background job thread (`start_job`), `run_batch`, `run_auto`, `run_sweep` (random order by default), `stop`, `reset_trip`, heartbeat thread. UI reads `rig.state`.
- `app.py` NiceGUI one-page dashboard (page `/`, 0.3 s refresh timer, ECharts for waveforms and heat maps).
- `selftest.py` tests with mocks of the firmware and of the Rigol.
- `firmware/spark_trigger/spark_trigger.ino` the Arduino sketch.

### Arduino protocol (115200 baud, one line per command, ends with LF)
`D <us>` -> `OK D` | `ERR range` (100..5000) ; `A` -> `OK ARMED` ; `X` -> `OK SAFE` ; `F` -> `OK FIRED` | `ERR not armed` | `ERR too soon` (100 ms);
`?` -> `D <us>` (heartbeat). Self-disarm after 3 s of silence prints `WDG SAFE`. The Arduino restarts when the port opens: wait 2 s, flush `READY`.
### Rigol commands used (DP832A, channel CH1)
`*IDN?`, `:APPL CH1,<V>,<A>`, `:OUTP CH1,ON|OFF`, `:MEAS:VOLT? CH1`, `:MEAS:CURR? CH1`, `:OUTP:OVP:VAL CH1,<V>`, `:OUTP:OVP CH1,ON`, `:SYST:ERR?`.
Exact syntax of the OVP commands is NOT yet confirmed on the real supply (see Rigol DP800 Programming Guide, chapter 2).

## Conventions
- Keep all hardware behind the device classes; every device has a Sim twin with the same API so the whole program runs without hardware.
- Any new behaviour needs a test in `selftest.py` (hardware-free) and, for UI, one in `tests/test_ui.py`.
- Keep the dashboard to ONE page: header (device lights, TRIP, STOP), controls, live graphs and numbers, tabs below (Shots, Sweep, Export, Log).
- Plain, short UI text for a beginner. Units in every label.

## Current status
- Done and tested in simulation: everything above (7 selftests, 4 UI tests, exports incl. PDF).
- NOT tested: real Rigol, real Arduino + firmware, real PicoScope, the visual look of the dashboard (no browser was available when it was written).
- PicoScope series of the team's scope is unknown: run `scope-check`. Only ps2000a and ps3000a are implemented; trigger is an analogue rising edge on channel A.

## Next steps (suggested order)
1. Run selftest, pytest and the dashboard on the user's PC; look at the page and fix layout problems.
2. Upload the firmware; test `Arduino` driver against the real board (`D`, `A`, `F`, `X`, watchdog).
3. Real Rigol with nothing connected: confirm command syntax, especially the OVP commands.
4. `scope-check`, then `scope-test`; extend `PicoScope` if the series is not 2000A/3000A (4000A/5000A use different calls).
5. Bench trigger-pulse check (pulse width vs dwell), then coil tests, supervised, low voltage first.
6. Calibrate: measured L and R of the coil, current-clamp scale (V/A), shunt value; replace the estimates in config.json.
7. Later: stage B (railplug) support: charge C2, HV charger control, relay K1, Rogowski coil channel, HV probe channel.

## Known traps (mistakes already made once)
- The user's breadboard counts columns from the RIGHT (column 1 at the right edge). Older guides in `docs/assets` use left-to-right numbers
  for the chips; `Breadboard_guide_my_board.pdf` is the correct one.
- Breadboard rails do not line up with column numbers; any hole on a rail strip is the same connection.
- The Rigol DP832A gives only 3 A; the coil's 7-9 A peaks come from the 10,000 uF capacitor at the coil (not 2200 uF).
- Code 104 = 0.1 uF = 100,000 pF (101 is 100 pF). The 1 MOhm grading resistors in stage B must be rated >= 1 kV.
- Team's design sheet estimates 3 mH / 0.5 ohm; with those, 12 V and 2 ms give 6.8 A and 69 mJ by hand. The team's sheet quoted about 7.6 A: check which assumptions it used.
