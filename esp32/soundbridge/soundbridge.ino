/*
 * Path: esp32/soundbridge/soundbridge.ino
 * SoundBridge - ESP32 Firmware
 * Sistema de captura de sinais Morse
 * 
 * Hardware:
 * - Botão: GPIO 5 (INPUT_PULLUP)
 * - LED Ponto (Azul): GPIO 12
 * - LED Traço (Vermelho): GPIO 13
 * 
 * Protocolo:
 * JSON simples via Serial (115200 baud)
 * {"type": "...", "value": "...", "timestamp": ...}
 */

#include <ArduinoJson.h>

// ── Pin definitions ──────────────────────────────────────────
static const uint8_t PIN_BUTTON   =  5;
static const uint8_t PIN_LED_DOT  = 12;   // blue  – dot
static const uint8_t PIN_LED_DASH = 13;   // red   – dash

// ── Timing constants (ms) ────────────────────────────────────
static const uint32_t DEBOUNCE_MS       =   50;
static const uint32_t DOT_THRESHOLD_MS  =  300;   // < 300 ms → dot
static const uint32_t LED_ON_MS         =  200;   // LED on duration
static const uint32_t LETTER_END_MS     = 1000;   // inactivity → letter end
static const uint32_t WORD_END_MS       = 2500;   // inactivity → word end

// ── State machine ────────────────────────────────────────────
enum class ButtonState { IDLE, PRESSED, DEBOUNCING_RELEASE };

static ButtonState  buttonState       = ButtonState::IDLE;
static uint32_t     pressStartMs      = 0;
static uint32_t     lastReleaseMs     = 0;
static uint32_t     debounceStartMs   = 0;
static bool         lastRawButton     = HIGH;  // INPUT_PULLUP → idle = HIGH

// Tracks which inactivity event has already been sent
static bool letterEndSent = false;
static bool wordEndSent   = false;

// ── LED state ────────────────────────────────────────────────
static uint32_t dotLedOnMs  = 0;
static uint32_t dashLedOnMs = 0;
static bool     dotLedActive  = false;
static bool     dashLedActive = false;

// ────────────────────────────────────────────────────────────
//  JSON helpers
// ────────────────────────────────────────────────────────────

/**
 * Serialise and print a JSON document to Serial.
 * All outgoing messages go through this single function.
 */
static void sendJson(JsonDocument &doc) {
    serializeJson(doc, Serial);
    Serial.println();   // newline makes line-framing easier for the host
}

static void sendSignal(const char *value) {
    StaticJsonDocument<128> doc;
    doc["type"]      = "signal";
    doc["value"]     = value;
    doc["timestamp"] = millis();
    sendJson(doc);
}

static void sendEvent(const char *eventType) {
    StaticJsonDocument<64> doc;
    doc["type"]      = eventType;
    doc["timestamp"] = millis();
    sendJson(doc);
}

static void sendSystemReady() {
    StaticJsonDocument<80> doc;
    doc["type"]      = "system";
    doc["message"]   = "ready";
    doc["timestamp"] = millis();
    sendJson(doc);
}

// ────────────────────────────────────────────────────────────
//  LED helpers
// ────────────────────────────────────────────────────────────

static void lightDotLed() {
    digitalWrite(PIN_LED_DOT, HIGH);
    dotLedOnMs   = millis();
    dotLedActive = true;
}

static void lightDashLed() {
    digitalWrite(PIN_LED_DASH, HIGH);
    dashLedOnMs   = millis();
    dashLedActive = true;
}

/** Called every loop iteration to auto-extinguish LEDs after LED_ON_MS. */
static void updateLeds() {
    uint32_t now = millis();

    if (dotLedActive && (now - dotLedOnMs >= LED_ON_MS)) {
        digitalWrite(PIN_LED_DOT, LOW);
        dotLedActive = false;
    }
    if (dashLedActive && (now - dashLedOnMs >= LED_ON_MS)) {
        digitalWrite(PIN_LED_DASH, LOW);
        dashLedActive = false;
    }
}

// ────────────────────────────────────────────────────────────
//  Signal classification
// ────────────────────────────────────────────────────────────

/**
 * Called once a complete press-release cycle has been measured.
 * Classifies the duration and triggers LED + JSON output.
 */
static void classifyAndSend(uint32_t durationMs) {
    if (durationMs < DOT_THRESHOLD_MS) {
        sendSignal(".");
        lightDotLed();
    } else {
        sendSignal("-");
        lightDashLed();
    }
}

// ────────────────────────────────────────────────────────────
//  Button state machine
// ────────────────────────────────────────────────────────────

/**
 * Non-blocking button handler.
 * Uses a simple state machine with software debounce on both
 * press and release edges.
 */
static void handleButton() {
    bool rawButton = digitalRead(PIN_BUTTON);   // LOW when pressed (INPUT_PULLUP)
    uint32_t now   = millis();

    switch (buttonState) {

        case ButtonState::IDLE:
            // Detect falling edge (button pressed)
            if (rawButton == LOW && lastRawButton == HIGH) {
                // Start debounce window
                debounceStartMs = now;
                buttonState = ButtonState::PRESSED;
                pressStartMs = now;
            }
            break;

        case ButtonState::PRESSED:
            // Wait out debounce, then watch for release
            if (rawButton == HIGH) {
                // Possible release – enter release-debounce
                debounceStartMs = now;
                buttonState = ButtonState::DEBOUNCING_RELEASE;
            }
            break;

        case ButtonState::DEBOUNCING_RELEASE:
            if (rawButton == LOW) {
                // Bounced back – still pressed
                buttonState = ButtonState::PRESSED;
            } else if (now - debounceStartMs >= DEBOUNCE_MS) {
                // Confirmed release
                uint32_t duration = now - pressStartMs;
                lastReleaseMs  = now;
                letterEndSent  = false;   // reset inactivity flags
                wordEndSent    = false;

                classifyAndSend(duration);
                buttonState = ButtonState::IDLE;
            }
            break;
    }

    lastRawButton = rawButton;
}

// ────────────────────────────────────────────────────────────
//  Inactivity / timing events
// ────────────────────────────────────────────────────────────

/**
 * Watches elapsed time since the last button release and emits
 * letter_end / word_end events exactly once per silence period.
 */
static void handleInactivity() {
    // Only relevant when the button is idle and at least one signal has been sent
    if (buttonState != ButtonState::IDLE || lastReleaseMs == 0) return;

    uint32_t elapsed = millis() - lastReleaseMs;

    if (!letterEndSent && elapsed >= LETTER_END_MS) {
        sendEvent("letter_end");
        letterEndSent = true;
    }

    if (!wordEndSent && elapsed >= WORD_END_MS) {
        sendEvent("word_end");
        wordEndSent = true;
    }
}

// ────────────────────────────────────────────────────────────
//  Arduino entry points
// ────────────────────────────────────────────────────────────

void setup() {
    Serial.begin(115200);
    while (!Serial) { /* wait for USB CDC on native USB boards */ }

    pinMode(PIN_BUTTON,   INPUT_PULLUP);
    pinMode(PIN_LED_DOT,  OUTPUT);
    pinMode(PIN_LED_DASH, OUTPUT);

    digitalWrite(PIN_LED_DOT,  LOW);
    digitalWrite(PIN_LED_DASH, LOW);

    // Brief startup blink to confirm power-on (blocking, intentional)
    digitalWrite(PIN_LED_DOT,  HIGH);
    digitalWrite(PIN_LED_DASH, HIGH);
    delay(300);
    digitalWrite(PIN_LED_DOT,  LOW);
    digitalWrite(PIN_LED_DASH, LOW);

    sendSystemReady();
}

void loop() {
    handleButton();
    handleInactivity();
    updateLeds();
}
