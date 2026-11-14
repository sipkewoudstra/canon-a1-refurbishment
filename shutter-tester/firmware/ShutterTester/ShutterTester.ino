/*
  Shutter Tester — two-channel focal-plane shutter timer            firmware v2
  Boards: Arduino Uno / Nano (ATmega328P) or Mega 2560, 16 MHz

  Channel A -> D2, Channel B -> D3          digital comparator outputs (interrupts)
  Level A   -> A0, Level B   -> A1          raw photodiode node
  Thresh A  -> A2, Thresh B  -> A3          OPTIONAL: trimmer wipers (U1 pin 2 / pin 6),
                                            lets the page show the threshold live

  MEASURE mode (default): every edge is timestamped with micros() in an interrupt
  (4 us resolution). A "shot" starts at the first edge and ends when both channels
  have been dark for QUIET_MS. One JSON line per shot. While idle, levels are
  reported every LEVEL_MS.

  CALIBRATE mode ('c' toggles): no shots are recorded. The analog inputs are sampled
  continuously and every CAL_MS one line reports the latest value, the min/max since
  the last line (shows flicker), the comparator states and how often each comparator
  flipped (shows chatter).

  Serial lines (newline-terminated JSON, 115200 baud):
    {"t":"hello","v":2,"light":1}
    {"t":"lvl","a":512,"b":498,"ta":250,"tb":240,"da":1,"db":0}
    {"t":"cal","a":512,"b":498,"amin":505,"amax":520,"bmin":490,"bmax":502,
     "ta":250,"tb":240,"da":1,"db":0,"fa":0,"fb":3}
    {"t":"shot","n":3,"a_on":0,"a_off":1012,"b_on":9840,"b_off":10860,"ea":2,"eb":2}
    {"t":"mode","cal":1}

  Commands (single characters): 'c' toggle calibrate, 'm' measure mode,
                                'l' toggle level streaming, 'r' reset shot counter
*/

#include <Arduino.h>

// ---- configuration ---------------------------------------------------------
const uint8_t PIN_A = 2;
const uint8_t PIN_B = 3;
const uint8_t LVL_A = A0, LVL_B = A1;
const uint8_t THR_A = A2, THR_B = A3;
const uint8_t LIGHT_LEVEL = HIGH;      // comparator output level when the sensor sees light
const unsigned long QUIET_MS = 300;    // shot ends after this much darkness on both channels
const unsigned long LEVEL_MS = 50;     // level report interval in measure mode (20 Hz)
const unsigned long CAL_MS = 40;       // report interval in calibrate mode (25 Hz)
const uint8_t MAX_EDGES = 32;          // per channel per shot

// ---- edge buffers (written in ISRs) ----------------------------------------
volatile unsigned long tA[MAX_EDGES], tB[MAX_EDGES];
volatile uint8_t sA[MAX_EDGES], sB[MAX_EDGES];   // 1 = became light, 0 = became dark
volatile uint8_t nA = 0, nB = 0;
volatile unsigned long lastEdgeUs = 0;
volatile bool active = false;
volatile uint16_t flipsA = 0, flipsB = 0;        // comparator flips, for calibrate mode

bool streamLevels = true;
bool calMode = false;
unsigned long shotCount = 0;
unsigned long lastReportMs = 0;

// calibrate-mode accumulators
int aMin = 1023, aMax = 0, bMin = 1023, bMax = 0, aLast = 0, bLast = 0;

static inline bool isLight(uint8_t pin) { return digitalRead(pin) == LIGHT_LEVEL; }

void isrA() {
  unsigned long t = micros();
  flipsA++;
  if (nA < MAX_EDGES) { tA[nA] = t; sA[nA] = isLight(PIN_A) ? 1 : 0; nA++; }
  lastEdgeUs = t; active = true;
}
void isrB() {
  unsigned long t = micros();
  flipsB++;
  if (nB < MAX_EDGES) { tB[nB] = t; sB[nB] = isLight(PIN_B) ? 1 : 0; nB++; }
  lastEdgeUs = t; active = true;
}

void setup() {
  pinMode(PIN_A, INPUT);   // comparator has its own pull-up
  pinMode(PIN_B, INPUT);
  Serial.begin(115200);
  attachInterrupt(digitalPinToInterrupt(PIN_A), isrA, CHANGE);
  attachInterrupt(digitalPinToInterrupt(PIN_B), isrB, CHANGE);
  Serial.println(F("{\"t\":\"hello\",\"v\":2,\"light\":1}"));
}

// first "became light" and last "became dark" for one channel, relative to t0
static void summarise(const unsigned long *t, const uint8_t *s, uint8_t n,
                      unsigned long t0, long &on, long &off) {
  on = -1; off = -1;
  for (uint8_t i = 0; i < n; i++) {
    if (s[i] == 1 && on < 0) on = (long)(t[i] - t0);
    if (s[i] == 0) off = (long)(t[i] - t0);
  }
  if (on >= 0 && off >= 0 && off < on) off = -1;  // ended light: incomplete
}

static void clearEdges() {
  noInterrupts(); nA = 0; nB = 0; active = false; interrupts();
}

void reportShot() {
  unsigned long a[MAX_EDGES], b[MAX_EDGES];
  uint8_t sa[MAX_EDGES], sb[MAX_EDGES], na, nb;
  noInterrupts();
  na = nA; nb = nB;
  for (uint8_t i = 0; i < na; i++) { a[i] = tA[i]; sa[i] = sA[i]; }
  for (uint8_t i = 0; i < nb; i++) { b[i] = tB[i]; sb[i] = sB[i]; }
  nA = 0; nB = 0; active = false;
  interrupts();

  if (na == 0 && nb == 0) return;
  unsigned long t0;
  if (na && nb) t0 = ((long)(b[0] - a[0]) < 0) ? b[0] : a[0];
  else t0 = na ? a[0] : b[0];

  long aOn, aOff, bOn, bOff;
  summarise(a, sa, na, t0, aOn, aOff);
  summarise(b, sb, nb, t0, bOn, bOff);

  shotCount++;
  Serial.print(F("{\"t\":\"shot\",\"n\":")); Serial.print(shotCount);
  Serial.print(F(",\"a_on\":"));  Serial.print(aOn);
  Serial.print(F(",\"a_off\":")); Serial.print(aOff);
  Serial.print(F(",\"b_on\":"));  Serial.print(bOn);
  Serial.print(F(",\"b_off\":")); Serial.print(bOff);
  Serial.print(F(",\"ea\":"));    Serial.print(na);
  Serial.print(F(",\"eb\":"));    Serial.print(nb);
  Serial.println('}');
}

static void printKV(const __FlashStringHelper *k, long v) { Serial.print(k); Serial.print(v); }

void reportMode() {
  Serial.print(F("{\"t\":\"mode\",\"cal\":")); Serial.print(calMode ? 1 : 0); Serial.println('}');
}

void handleCommands() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == 'l') streamLevels = !streamLevels;
    else if (c == 'r') shotCount = 0;
    else if (c == 'c' || c == 'm') {
      calMode = (c == 'c') ? !calMode : false;
      clearEdges();
      noInterrupts(); flipsA = flipsB = 0; interrupts();
      aMin = bMin = 1023; aMax = bMax = 0;
      reportMode();
    }
  }
}

void loopCalibrate() {
  // sample continuously; report every CAL_MS
  aLast = analogRead(LVL_A); bLast = analogRead(LVL_B);
  if (aLast < aMin) aMin = aLast; if (aLast > aMax) aMax = aLast;
  if (bLast < bMin) bMin = bLast; if (bLast > bMax) bMax = bLast;
  clearEdges();                                  // no shots while calibrating

  if (millis() - lastReportMs >= CAL_MS) {
    lastReportMs = millis();
    uint16_t fa, fb;
    noInterrupts(); fa = flipsA; fb = flipsB; flipsA = flipsB = 0; interrupts();
    int ta = analogRead(THR_A), tb = analogRead(THR_B);
    printKV(F("{\"t\":\"cal\",\"a\":"), aLast); printKV(F(",\"b\":"), bLast);
    printKV(F(",\"amin\":"), aMin); printKV(F(",\"amax\":"), aMax);
    printKV(F(",\"bmin\":"), bMin); printKV(F(",\"bmax\":"), bMax);
    printKV(F(",\"ta\":"), ta);     printKV(F(",\"tb\":"), tb);
    printKV(F(",\"da\":"), isLight(PIN_A) ? 1 : 0); printKV(F(",\"db\":"), isLight(PIN_B) ? 1 : 0);
    printKV(F(",\"fa\":"), fa);     printKV(F(",\"fb\":"), fb);
    Serial.println('}');
    aMin = bMin = 1023; aMax = bMax = 0;
  }
}

void loopMeasure() {
  // end of shot: both channels dark and no edges for QUIET_MS
  if (active) {
    noInterrupts();
    unsigned long last = lastEdgeUs;
    interrupts();
    bool dark = !isLight(PIN_A) && !isLight(PIN_B);
    if (dark && (micros() - last) > QUIET_MS * 1000UL) reportShot();
  }
  // levels only while idle, so serial traffic never delays a report
  if (streamLevels && !active && millis() - lastReportMs >= LEVEL_MS) {
    lastReportMs = millis();
    printKV(F("{\"t\":\"lvl\",\"a\":"), analogRead(LVL_A)); printKV(F(",\"b\":"), analogRead(LVL_B));
    printKV(F(",\"ta\":"), analogRead(THR_A)); printKV(F(",\"tb\":"), analogRead(THR_B));
    printKV(F(",\"da\":"), isLight(PIN_A) ? 1 : 0); printKV(F(",\"db\":"), isLight(PIN_B) ? 1 : 0);
    Serial.println('}');
  }
}

void loop() {
  handleCommands();
  if (calMode) loopCalibrate(); else loopMeasure();
}
