# Spark ignitor test bench

One program that controls the Arduino trigger, the Rigol supply and the PicoScope, measures every shot,
stops when a safety check fires, and shows everything on **one web page** with exports (CSV, raw waveforms,
PNG graphs, PDF report).

It starts in **simulation**, so you can try everything before any hardware is connected.

See **`docs/OPERATING_GUIDE.md`** for the full step-by-step manual (setup, dashboard
walkthrough, hardware bring-up order, a session checklist, trip troubleshooting, glossary),
and **`docs/APP_GUIDE.md`** for a detailed reference on the dashboard's controls and — in
depth — exactly what gets logged, where, and in what format. This README is just the short
version.

## 1. Install (Windows)
Full step-by-step guide for a new PC: **`SETUP.md`**.

1. Install Python 3.12 (or 3.10 or newer) from python.org. Tick "Add python.exe to PATH".
2. Double-click **`setup.bat`** once. It creates `.venv`, installs everything in `requirements.txt`, and runs the selftest.
   It must end with `SETUP COMPLETE`.
3. Double-click **`START_DASHBOARD.bat`** and open the address it shows (**http://localhost:8080**, or 8081 if 8080 is busy).
   Keep the black window open while you use the page.

## 2. Try it in simulation
Press **Connect**, then **Fire once** or **Run batch**. The waveform, the numbers and the shot table update after each shot.
Open the **Sweep** tab and press **Start sweep** to get the colour maps. The **Export** tab saves everything.
The simulated coil uses L = 3 mH and R = 0.5 ohm. Simulated results are not measurements.

## 3. Go to real hardware, step by step
Do these in order. Do not connect the coil until step 5 works.

1. **Arduino:** open `firmware/spark_trigger/spark_trigger.ino` in the Arduino IDE and upload it (board: Arduino Uno).
2. **Find the devices:** `python -m spark_ignitor ports` lists the COM port and the Rigol's VISA name.
3. **PicoScope:** close PicoScope 7, install the PicoSDK (same 32/64-bit as Python), then run
   `python -m spark_ignitor scope-check`. It tells you the series. Support here: `ps2000a`, `ps3000a` and `ps5000a`.
4. **Edit `config.json`** (create it with `python -m spark_ignitor init-config`): set `arduino_mode`, `rigol_mode`
   to `real`, `arduino_port`, `rigol_resource`, `scope_mode`, and your measured `L_mH`, `R_ohm`, `clamp_V_per_A`, `shunt_ohm`.
   Then `python -m spark_ignitor scope-test` captures one block without a trigger to check the scope settings.
5. **Step by step on the dashboard:** first only the Arduino real (Rigol and scope simulated), then add the Rigol
   (nothing connected to its output), then the scope, and the coil last, with someone present and the enclosure closed.

## 4. What is tested and what is not
| Part | Status |
|---|---|
| Physics, metrics, safety checks, batches, sweeps, exports | tested here (`selftest`) |
| Arduino command protocol incl. watchdog | tested against a mock of the firmware |
| Rigol command strings | tested against a mock; the supply's own error report is checked after every command |
| Dashboard buttons, trip display, STOP | tested with a simulated browser |
| **Real Rigol, real Arduino, real PicoScope** | **not tested: the first bench run will need adjustments** |
| PicoScope code | written from Pico's published example and the installed `picosdk` signatures |

## 5. Safety
- Every run arms the coil itself and switches the Rigol off and disarms the Arduino when it ends, stops, or trips.
- Trips: peak current above `I_trip_A`, Rigol voltage differing from the setting, dwell or voltage above the limits,
  too many misfires in a row, Arduino watchdog or heartbeat failure, any device error.
- The Rigol's own over-voltage trip is set from `ovp_V` (the default of the supply is 33 V, which protects nothing).
- Software is the second line of defence. The first line is hardware: fuse, e-stop, enclosure, discharge stick.
- Never touch the rig with power on. Discharge the big capacitor before moving a wire.

## 6. Files
```
spark_ignitor/   the program (config, arduino, rigol, scope, analysis, safety, storage, report, rig, app, cli)
firmware/        Arduino sketch
tests/           dashboard tests (pytest)
config.json      your settings
data/            every run is saved here in its own folder (shots.csv, settings.json, waveforms, reports)
```
