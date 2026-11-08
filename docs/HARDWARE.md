# Hardware reference (stage A', the LabVIEW/Python version)

## Coil
Audi A5 3.2 L 4-pin COP coil with IGBT inside. Pins: 1 = +12 V, 2 = signal ground (driver ground), 3 = trigger (5 V pulse; coil charges while HIGH and fires when it drops), 4 = power ground.
Team design ties pins 2 and 4 together to ground. Typical dwell 2-3 ms. Estimated primary: 3 mH, 0.5 ohm (to be measured).
Dwell 2 ms at 12 V: I = 12/0.5*(1-exp(-2ms*0.5/3mH)) = 6.8 A, E = 69 mJ. Never run the coil with the plug disconnected.

## Power chain (left to right)
Rigol DP832A CH1 (12 V, 3 A limit, OVP 14 V) -> F1 5 A slow-blow -> relay K_ES contact (12 V automotive relay 30-40 A; its coil is fed from the F1 output through the e-stop (NC) and the door switch to ground; 1N4007 flyback diode across the coil)
-> terminal block TB1 +12 V group -> two branches: (a) thick 1.5 mm2 wire to coil pin 1 with C_BULK 10,000 uF 35 V (low ESR) and R_BLD 470 ohm 1 W bleed resistor on that wire next to the coil, and the current clamp around it (PicoScope A);
(b) thin wire (E1) to the 7805 IN on the breadboard (a few mA only).
TB1 is a 3-position barrier strip, two screws per number joined by a plate: position 1 = +12 V; positions 2 and 3 joined by a short wire = ground star point. Max two ring terminals per screw. Check continuity before wiring.

## Ground rules
Single-point ground at TB1 GND. Rigol minus, C_BULK minus, R_BLD, coil pins 2+4, K_ES coil, PicoScope probe grounds, breadboard ground (E2: bottom minus rail), shunt return all go there.
Arduino GND goes ONLY to optocoupler pin 3 (cathode side), never to any breadboard rail. The Arduino is powered by USB.

## Breadboard (user's EIC-1104 style board; columns counted from the RIGHT, column 1 at right edge; rows A-E top half, F-J bottom half)
Rails: top + (upper row), top - (lower row), bottom + (upper), bottom - (lower). Any hole on a rail strip is the same connection. Rail holes do not line up with columns.
All chips: notch to the LEFT; pin 1 is the bottom-left pin. Row letters below are suggestions; if jumper housings collide use another row of the same column and half.

| Step | Item | Holes |
|---|---|---|
| 1 | red jumper top + to bottom + (right end); black top - to bottom - | keep columns 1-2 free |
| 2 | U2 7805 standing, printed side toward you | E30 IN, E29 GND, E28 OUT |
| 2 | C_IN 0.33 uF (334) | C30-C29 |
| 2 | C_OUT 0.1 uF (104) | A29-A28 |
| 2 | black jumper B29 to top - ; red jumper C28 to top + | |
| 3 | U3 6N137 | pins 1-4 = F6 F5 F4 F3; pins 8-5 = E6 E5 E4 E3 |
| 3 | red jumper A6 to top + (pin 8); short bare link C6-C5 (pin 7 to pin 8); black jumper A3 to top - (pin 5) | |
| 3 | C_BYP 0.1 uF (104) | D6-D3 |
| 3 | R_PU 1 kohm (brown-black-red-gold) | top + to B4 (pin 6) |
| 4 | R_IN 330 ohm (orange-orange-brown-gold) | H7-H5 (pin 2) |
| 4 | Arduino D9 wire to J7 ; Arduino GND wire to J4 (pin 3) | Arduino side only |
| 5 | U4 74HC14 | pins 1-7 = F16..F10 ; pins 14-8 = E16..E10 |
| 5 | red jumper A16 to top + (pin 14) ; C_DEC 0.1 uF between top + and top - (own holes) | |
| 5 | black jumper J10 to bottom - (pin 7) ; C15, A13, A11 to top - (pins 13, 11, 9) ; J14, J12 to bottom - (pins 3, 5) | unused inputs grounded |
| 5 | green jumper C4 to G16 | 6N137 pin 6 (VO) to 74HC14 pin 1 |
| 6 | R_G 100 ohm (brown-black-brown-gold) | H15-H25 (pin 2 to Q1 base) |
| 6 | Q1 2N2222 (E,B,C) | J26, J25, J24 (flat face toward you; confirm pinout) |
| 6 | Q2 2N3906 (E,B,C) | J22, J21, J20 |
| 6 | green jumpers G25-G21 (bases) and F26-F22 (emitters); red F24 to bottom + (Q1 collector); black F20 to bottom - (Q2 collector) | |
| 7 | E1: thin +12 V wire from TB1 to A30 ; E2: bottom - rail (near column 31) to TB1 GND ; E3: trigger from H26 to coil pin 3 (shielded or twisted) | do last |

Before power: continuity checks (+5 rail vs - rail must NOT beep; Arduino GND hole J4 vs any - rail must NOT beep; pins 8/14 to + rail and pins 5/7 to - rail must beep).
First power-up: only E1 and E2 connected, Rigol 12 V with current limit 0.2 A, expect 5 V between the top rails. Then Arduino D9/GND with an LED + 330 ohm on the trigger line. Coil last.

## PicoScope hookup
Channel A: current clamp around the +12 V wire after C_BULK (scale in config `clamp_V_per_A`, assumed 0.1). Channel B: across R_SH (10 ohm). Trigger: analogue rising edge on A at 0.05 V (or digital D0 / external if the scope has one; not implemented yet).
Window 10 ms, about 2 us per sample (5000 samples), 10 % pre-trigger. Probe grounds to the single ground point. PicoScope 7 must be closed while the program uses the scope.

## Part notes
- Resistors: fixed 1/4 W carbon or metal film (not trimmers/potentiometers). Chinese shop names: 固定電阻, 色環電阻; cement resistor = 水泥電阻; variable = 可變電阻 / 電位器.
- 1N5408 (3 A, 1000 V) x20 bought; 1 Mohm HV resistors need >= 1 kV rating; TVS: P6KE15CA (bidirectional).
- Wire: Dupont 24 AWG jumpers on the breadboard (thicker than about 0.8 mm damages the contacts); 1.5 mm2 for coil current; shielded 2-core for the trigger line to the coil; ring terminals on the terminal block.
- Colour convention: red +5 V/+12 V, black ground, green signal, blue Arduino D9, gray Arduino GND, yellow trigger, orange +12 V thin wire.
