# Project context (everything decided so far)

This document summarises a long conversation with Claude (chat) so that work can continue in Claude Code.

## 1. The big picture
- Team project, supervised by a professor with regular progress meetings. Goal: a **railplug** igniter (two parallel rails; a spark
  starts at the breech end and a large current pulse from a capacitor drives the arc along the rails).
- Built in stages, from a team parts list based on the YouTube video "Coil Pack Driver Circuit / Arduino / 555 Timer" (0033mer) and two
  railplug reports (DOE/ER/12115-2; UT/DOE railplug ignition report):
  - **Stage A (555 version):** Audi A5 3.2 L 4-pin COP coil (IGBT inside), NE555 timer fires it at a fixed dwell about 3 ms and rate about 8.33 Hz. Team parts: 7805, 555 with R_A 8.2 k, R_B 330 k, C_T 0.47 uF, 1N4148; 5 A fuse; 2200 uF capacitor.
  - **Stage A' (Arduino version) = the user's work:** the 555 is replaced by an Arduino so the computer can set the dwell. Driver: Arduino D9 -> 330 ohm -> 6N137 optocoupler -> 74HC14 inverter (fail-safe: coil stays off if the Arduino resets) -> 100 ohm -> 2N2222/2N3906 emitter follower -> coil pin 3.
  - **Stage B (railplug, NOT built yet):** breakdown path: coil HV -> C1 (2-5 nF, >=30 kV, blocks follow-on current) -> HV node with SG1 protective gap (about 8 kV on the bench) -> railplug.
    Follow-on path: C2 100 uF charged to about 200 V (about 2 J) through relay K1 from an HV charger, discharged through the diode stack D1 (1N5408 x15 in series, each with a 1 Mohm grading resistor rated >= 1 kV; the 1 Mohm string also acts as R2), air-core inductor of a few uH, bleed resistor 100 kohm across C2. Needs an HV probe (1000:1, >=40 kV) and a Rogowski or Pearson current monitor (hundreds of A).
- The user's role: **everything connecting the computer to the spark plug** (control, measurement, safety, logging, UI).

## 2. Equipment status
- Available: Rigol DP832A (CH1 30 V / 3 A), a PicoScope (**series unknown**; came with two x10 probes, a USB 3.0 cable and a digital/MSO-style cable with logic clips, so it may be an MSO model), Arduino Uno R3 (blue clone, may need a CH340 driver), large breadboard (EIC-1104 style, columns counted from the right), KILTER 325 multimeter, soldering stand, tip cleaner, desoldering pump, cutters, terminal block (3-position barrier strip, two joined screws per number).
- Bought at an electronics shop in Taiwan (see `docs/assets/Electronic_Parts_Quote_List_EN.xlsx`): ICs (7805, 6N137, 74HC14, 2N2222, 2N3906), resistors, capacitors (104 = 0.1 uF, 334 = 0.33 uF, 10,000 uF 35 V electrolytic), relay with socket, e-stop button, fuse parts, terminal block, wire (thick red/black 1.5 mm2, shielded 2-core, blue wire), Dupont jumper sets, enclosure box, 1N5408 diodes, 1 Mohm resistors, cement resistors, etc.
- Still to get or borrow: current clamp (Pico TA189 was suggested; datasheet claims about 30 A, DC-100 kHz, 100 mV/A: confirm), USB isolator for the PicoScope (Intona 7054 suggested; required before stage B), HV probe (borrow), Rogowski/Pearson (borrow), HV charger, C1, C2, HV relay, railplug body parts.
- No browser/hardware was available to the assistant; nothing has been run on the real devices.

## 3. Key design decisions and why
1. **No LabVIEW.** A LabVIEW guide (13 pages, `LabVIEW_build_guide.pdf`) was written first, then the user confirmed LabVIEW is not required and asked for a Python program with a one-page "landing page" showing everything and exporting data. The guide is legacy; keep it only as a description of the intended logic.
2. **Rigol is 3 A max** -> a 10,000 uF capacitor at the coil supplies the 7-9 A dwell peaks (the team's 2200 uF would sag about 1.3-3 V). Set Rigol OVP to 14 V (default 33 V). Leave OCP at default; the supply's current limit holds at 3 A.
3. **Measurement without probing the primary voltage:** the IGBT is inside the coil, so the primary voltage cannot be probed. Instead: channel A = coil current with a clamp on the +12 V wire after the capacitor; channel B = spark current as the voltage across a 10 ohm non-inductive shunt R_SH (with a bidirectional 15 V TVS across it) in the plug-shell ground lead (stage A only: in stage B hundreds of amps flow in that rail, so use the Rogowski coil instead).
4. **Isolation:** Arduino ground connects to the board only through the optocoupler. A USB isolator on the PicoScope stops the PC bypassing the barrier (required in stage B).
5. **Single-point ground** at terminal block TB1 (star). Coil pins 2 and 4 tied together and grounded. Plug shell grounded.
6. **Safety layers:** fuse 5 A slow-blow, e-stop (NC) + door switch drive relay K_ES that cuts +12 V, bleed resistor 470 ohm across the big capacitor, Arduino firmware caps (dwell <= 5000 us, 100 ms rest, 3 s watchdog), software trips (see CLAUDE.md).
7. **Firing sequence in software:** arm the scope (RunBlock) first, then fire, then read; rest between shots (coil heating); sweeps shuffle the order.
8. **Exports requested by the user:** CSV shot table, raw waveforms, PNG graphs, PDF report (all implemented). UI language: English.
9. **Real-time:** timing-critical parts run on hardware (Arduino timer for dwell, scope sampling). The PC only needs to show each shot about 0.2-0.5 s after it fires; 2-5 shots/s is the practical limit (and the coil needs rest anyway).

## 4. What stage A should yield (data the dashboard is meant to collect)
Trigger pulse width vs set dwell; coil current ramp and peak; stored energy 0.5*L*I^2; inductance from the ramp slope (L = V / (dI/dt)); spark current and burn time from the shunt; misfire rate (0 misfires in N shots only proves a rate below about 3/N at 95 %); shot-to-shot spread; a voltage-dwell map of reliability. It cannot give breakdown voltage or delivered energy (needs the HV probe) or real in-cylinder performance (bench air at atmospheric pressure).

## 5. Open questions / unknowns
- PicoScope series (run `scope-check`); does it have digital inputs or an external trigger input (then a digital/external trigger is better than analogue channel A).
- Real values: coil L and R (LCR meter or the ramp fit), current-clamp scale and range, Rigol VISA resource name, Arduino COM port.
- Lab PC: operating system (Windows assumed) and whether Python is installed.
- Exact Rigol OVP command syntax on the real unit; the code checks `:SYST:ERR?` and will report a rejection.
- Do the coil's pins 2 and 4 really need tying and does the coil trigger threshold work with the emitter-follower output (about 4.3 V high)? Confirm with the scope.
- What the professor expects to be shown at the next progress meeting.

## 6. Corrections made during the conversation (do not repeat these errors)
- Hole addresses in the first breadboard figures (A-1L, workbook sheet "A-1L") used left-to-right numbering; the user's board counts right-to-left. `Breadboard_guide_my_board.pdf` fixes this (U3 6N137: pin 1 at F6; U4 74HC14: pin 1 at F16, notch to the left).
- A 104 capacitor is 0.1 uF (not 101). 7805 (positive 5 V) must not be replaced by 7905 (negative). 6N137 equivalents: HCPL-2601, HCPL-2611 (not PC817). TVS must be bidirectional (P6KE15CA or 1.5KE15CA). Shunt must be non-inductive (no wire-wound).
- Two things were once drawn into the same rail hole; every rail connection must use its own hole.
- A team BOM item listed 1/4 W 1 Mohm grading resistors: they need a >= 1 kV rating (e.g. Vishay VR25 style).
- The 555 parts (NE555, R_A, R_B, D_T, C_T, C_CV, LED) are only for the optional first coil test; they are not used in the LabVIEW/Python version.
- Simulation uses L = 3 mH, R = 0.5 ohm (team estimates). Sim spark rule: sparks if stored energy >= 15 mJ, burn = E/45 ms, spark current 60 mA, noise 30 mA (coil) and 1.5 mA (spark).

## 7. Files in docs/assets
| File | What it is |
|---|---|
| `Fig_S-1_whole_system.png` | whole system overview (power, breadboard driver, coil, scope) |
| `Breadboard_guide_my_board.pdf` | 10-page step-by-step breadboard build for the user's board (correct hole names) |
| `Breadboard_final_my_board.png` | the finished breadboard |
| `fig_A-2L_EN.png`, `fig_B-1L_EN.png` | schematics: spark plug driver (A-2L) and railplug breakdown path (B-1L) |
| `railplug_circuit_build_bilingual.xlsx` | the team's railplug manual, English + Chinese switch, updated BOM and new sheets (A-1L uses old hole numbers) |
| `spark_plug_breadboard_parts_EN.xlsx` | the team's parts list with use/system labels and the LabVIEW additions |
| `Electronic_Parts_Quote_List_EN.xlsx` | the list sent to the electronics shop (English copy) |
| `LabVIEW_build_guide.pdf` | legacy LabVIEW plan (not needed any more) |
| `SIMULATED_example_report.pdf` | example PDF export from a simulated run |

## 8. Good first prompt for Claude Code
"Read CLAUDE.md, docs/PROJECT_CONTEXT.md and docs/HARDWARE.md. Set up a Python virtual environment, install requirements, run the selftest and the pytest suite, then start the dashboard in simulation and tell me what you see. I am a beginner, so explain each step."
