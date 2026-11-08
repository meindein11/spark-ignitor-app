// Spark ignitor trigger firmware (Arduino Uno R3, output on pin D9)
//
// Commands: one text line each, ending with a line feed, 115200 baud
//   D <us>   set the dwell in microseconds (100 to 5000)   -> OK D     | ERR range
//   A        arm                                            -> OK ARMED
//   X        disarm                                         -> OK SAFE
//   F        fire one shot (only when armed)                -> OK FIRED | ERR not armed | ERR too soon
//   ?        heartbeat, answers with the dwell              -> D <us>
//
// Safety built in:
//   - the dwell can never be set above 5000 us
//   - at least 100 ms between two shots
//   - it disarms itself after 3 s without any command and prints WDG SAFE
//   - the trigger pin is LOW at start-up and after every shot

const uint8_t TRIG_PIN = 9;
const unsigned int MAX_DWELL_US = 5000;
const unsigned int MIN_DWELL_US = 100;
const unsigned long MIN_REST_MS = 100;
const unsigned long WATCHDOG_MS = 3000;

unsigned int dwell_us = 1000;
unsigned long lastShot = 0;
unsigned long lastCmd = 0;
bool armed = false;

void setup() {
  pinMode(TRIG_PIN, OUTPUT);
  digitalWrite(TRIG_PIN, LOW);
  Serial.begin(115200);
  Serial.setTimeout(50);
  Serial.println("READY");
}

void fire() {
  noInterrupts();                       // exact timing: nothing may interrupt the pulse
  digitalWrite(TRIG_PIN, HIGH);         // the coil charges while this pin is HIGH
  delayMicroseconds(dwell_us);
  digitalWrite(TRIG_PIN, LOW);          // the spark happens when it drops
  interrupts();
  lastShot = millis();
}

void loop() {
  if (armed && millis() - lastCmd > WATCHDOG_MS) {   // the PC went silent
    armed = false;
    digitalWrite(TRIG_PIN, LOW);
    Serial.println("WDG SAFE");
  }
  if (!Serial.available()) return;

  String s = Serial.readStringUntil('\n');
  s.trim();
  lastCmd = millis();

  if (s.startsWith("D ")) {
    long v = s.substring(2).toInt();
    if (v >= MIN_DWELL_US && v <= MAX_DWELL_US) { dwell_us = (unsigned int)v; Serial.println("OK D"); }
    else Serial.println("ERR range");
  } else if (s == "A") {
    armed = true; Serial.println("OK ARMED");
  } else if (s == "X") {
    armed = false; digitalWrite(TRIG_PIN, LOW); Serial.println("OK SAFE");
  } else if (s == "F") {
    if (!armed) Serial.println("ERR not armed");
    else if (millis() - lastShot < MIN_REST_MS) Serial.println("ERR too soon");
    else { fire(); Serial.println("OK FIRED"); }
  } else if (s == "?") {
    Serial.print("D "); Serial.println(dwell_us);
  } else {
    Serial.println("ERR unknown");
  }
}
