/*
 * Path: esp32/soundbridge/soundbridge.ino
 * SoundBridge – ESP32 Firmware
 * Morse code capture + HTTP polling for latest message
 *
 * Hardware:
 *   Button : GPIO 5  (INPUT_PULLUP)
 *   LED dot  (Blue) : GPIO 12
 *   LED dash (Red)  : GPIO 13
 *
 * Dependencies (install via Arduino Library Manager):
 *   - ArduinoJson  ≥ 6.x
 *   - WiFi         (built-in ESP32 core)
 *   - HTTPClient   (built-in ESP32 core)
 *
 * Configuration:
 *   Edit the constants in the "User Config" section below.
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <TFT_eSPI.h>

TFT_eSPI tft = TFT_eSPI();

// ════════════════════════════════════════════════════════════
//  User Config  ← edit these
// ════════════════════════════════════════════════════════════

static const char*    WIFI_SSID        = "NOWO-2ECA4";
static const char*    WIFI_PASSWORD    = "64Sw3kccmWmT";

// IP (or hostname) of the machine running the FastAPI server
static const char*    API_HOST         = "192.168.0.15";
static const uint16_t API_PORT         = 8000;

// How often the ESP32 polls /morse/latest (milliseconds)
static const uint32_t POLL_INTERVAL_MS = 5000;

// ════════════════════════════════════════════════════════════
//  Pin definitions
// ════════════════════════════════════════════════════════════

static const uint8_t PIN_BUTTON   =  5;
static const uint8_t PIN_LED_DOT  = 12;   // blue  – dot
static const uint8_t PIN_LED_DASH = 13;   // red   – dash

// ════════════════════════════════════════════════════════════
//  Timing constants (ms)
// ════════════════════════════════════════════════════════════

static const uint32_t DEBOUNCE_MS      =   50;
static const uint32_t DOT_THRESHOLD_MS =  300;   // < 300 ms → dot
static const uint32_t LED_ON_MS        =  200;
static const uint32_t LETTER_END_MS    = 1000;   // inactivity → letter_end
static const uint32_t WORD_END_MS      = 2500;   // inactivity → word_end

// ════════════════════════════════════════════════════════════
//  Button state machine
// ════════════════════════════════════════════════════════════

enum class ButtonState { IDLE, PRESSED, DEBOUNCING_RELEASE };

static ButtonState buttonState     = ButtonState::IDLE;
static uint32_t    pressStartMs    = 0;
static uint32_t    lastReleaseMs   = 0;
static uint32_t    debounceStartMs = 0;
static bool        lastRawButton   = HIGH;

static bool letterEndSent = false;
static bool wordEndSent   = false;

// ════════════════════════════════════════════════════════════
//  LED state
// ════════════════════════════════════════════════════════════

static uint32_t dotLedOnMs    = 0;
static uint32_t dashLedOnMs   = 0;
static bool     dotLedActive  = false;
static bool     dashLedActive = false;

// ════════════════════════════════════════════════════════════
//  Polling state
// ════════════════════════════════════════════════════════════

static uint32_t lastPollMs  = 0;
static int      lastSeenId  = -1;   // ID of the last record we processed

// ════════════════════════════════════════════════════════════
//  UI
// ════════════════════════════════════════════════════════════

void drawUI(const char* text, const char* morse) {
    tft.fillScreen(TFT_BLACK);

    // Texto traduzido (maior destaque)
    tft.setTextColor(TFT_GREEN, TFT_BLACK);
    tft.setTextSize(2);
    tft.setCursor(10, 10);
    tft.println("Texto:");

    tft.setTextColor(TFT_WHITE, TFT_BLACK);
    tft.setCursor(10, 35);
    tft.println(String(text).substring(0, 20));

    // Morse (mais espaço e mais pequeno)
    tft.setTextColor(TFT_YELLOW, TFT_BLACK);
    tft.setTextSize(2);
    tft.setCursor(10, 80);
    tft.println("Morse:");

    tft.setCursor(10, 100);
    tft.println(String(morse).substring(0, 50)); // mais caracteres
}

// ════════════════════════════════════════════════════════════
//  WiFi helpers
// ════════════════════════════════════════════════════════════

void connectWiFi() {
    Serial.printf("[WiFi] Connecting to %s", WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    // Block until connected (runs once at startup only)
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }

    Serial.printf("\n[WiFi] Connected. IP: %s\n",
                  WiFi.localIP().toString().c_str());
}

// ════════════════════════════════════════════════════════════
//  JSON / Serial helpers
// ════════════════════════════════════════════════════════════

static void sendJson(JsonDocument& doc) {
    serializeJson(doc, Serial);
    Serial.println();
}

static void sendSignal(const char* value) {
    StaticJsonDocument<128> doc;
    doc["type"]      = "signal";
    doc["value"]     = value;
    doc["timestamp"] = millis();
    sendJson(doc);
}

static void sendEvent(const char* eventType) {
    StaticJsonDocument<64> doc;
    doc["type"]      = eventType;
    doc["timestamp"] = millis();
    sendJson(doc);
}

static void sendSystemReady() {
    StaticJsonDocument<80> doc;
    doc["type"]    = "system";
    doc["message"] = "ready";
    doc["timestamp"] = millis();
    sendJson(doc);
}

// ════════════════════════════════════════════════════════════
//  LED helpers
// ════════════════════════════════════════════════════════════

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

// ════════════════════════════════════════════════════════════
//  Signal classification
// ════════════════════════════════════════════════════════════

static void classifyAndSend(uint32_t durationMs) {
    if (durationMs < DOT_THRESHOLD_MS) {
        sendSignal(".");
        lightDotLed();
    } else {
        sendSignal("-");
        lightDashLed();
    }
}

// ════════════════════════════════════════════════════════════
//  Button state machine
// ════════════════════════════════════════════════════════════

static void handleButton() {
    bool     rawButton = digitalRead(PIN_BUTTON);
    uint32_t now       = millis();

    switch (buttonState) {
        case ButtonState::IDLE:
            if (rawButton == LOW && lastRawButton == HIGH) {
                debounceStartMs = now;
                buttonState     = ButtonState::PRESSED;
                pressStartMs    = now;
            }
            break;

        case ButtonState::PRESSED:
            if (rawButton == HIGH) {
                debounceStartMs = now;
                buttonState     = ButtonState::DEBOUNCING_RELEASE;
            }
            break;

        case ButtonState::DEBOUNCING_RELEASE:
            if (rawButton == LOW) {
                buttonState = ButtonState::PRESSED;
            } else if (now - debounceStartMs >= DEBOUNCE_MS) {
                uint32_t duration = now - pressStartMs;
                lastReleaseMs = now;
                letterEndSent = false;
                wordEndSent   = false;
                classifyAndSend(duration);
                buttonState = ButtonState::IDLE;
            }
            break;
    }

    lastRawButton = rawButton;
}

// ════════════════════════════════════════════════════════════
//  Inactivity / timing events
// ════════════════════════════════════════════════════════════

static void handleInactivity() {
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

// ════════════════════════════════════════════════════════════
//  HTTP Polling  –  GET /morse/latest
// ════════════════════════════════════════════════════════════

/*
 * Called every POLL_INTERVAL_MS.
 *
 * Possible API responses:
 *
 *   A) Table empty:
 *      {"status": "empty"}
 *
 *   B) Record found:
 *      {"id": 7, "device_id": "esp32_01", "morse": "... --- ...",
 *       "text": "SOS", "timestamp": "2024-05-01T12:00:00"}
 *
 * The ESP32 only acts on a record if its id is different from the
 * last one it already processed (lastSeenId), so the same message
 * is never handled twice between resets.
 */
static void pollLatestMessage() {
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("[poll] WiFi not connected – skipping.");
        return;
    }

    // Build URL: http://<host>:<port>/morse/latest
    char url[128];
    snprintf(url, sizeof(url), "http://%s:%d/morse/latest", API_HOST, API_PORT);

    HTTPClient http;
    http.begin(url);
    http.setTimeout(3000);          // 3 s max – won't block the loop long

    int httpCode = http.GET();

    if (httpCode != HTTP_CODE_OK) {
        Serial.printf("[poll] HTTP error: %d\n", httpCode);
        http.end();
        return;
    }

    String body = http.getString();
    http.end();

    // Parse JSON
    StaticJsonDocument<256> doc;
    DeserializationError err = deserializeJson(doc, body);
    if (err) {
        Serial.printf("[poll] JSON parse error: %s\n", err.c_str());
        return;
    }

    // ── Case A: empty table ──────────────────────────────────
    if (doc.containsKey("status")) {
        Serial.println("[poll] No messages in database yet.");
        return;
    }

    // ── Case B: record received ──────────────────────────────
    int         id        = doc["id"]        | -1;
    const char* deviceId  = doc["device_id"] | "?";
    const char* morse     = doc["morse"]     | "";
    const char* text      = doc["text"]      | "";

    // Skip if we already processed this record
    if (id == lastSeenId) {
        Serial.printf("[poll] No new message (latest id=%d).\n", id);
        return;
    }

    // New message – handle it
    lastSeenId = id;
    drawUI(text, morse);

    // ── Add your own logic here ──────────────────────────────
    // Example: blink both LEDs twice to signal a new message
    for (int i = 0; i < 2; i++) {
        digitalWrite(PIN_LED_DOT,  HIGH);
        digitalWrite(PIN_LED_DASH, HIGH);
        delay(150);
        digitalWrite(PIN_LED_DOT,  LOW);
        digitalWrite(PIN_LED_DASH, LOW);
        delay(150);
    }
}

// ════════════════════════════════════════════════════════════
//  Arduino entry points
// ════════════════════════════════════════════════════════════

void setup() {
    Serial.begin(115200);
    while (!Serial) { /* wait for USB CDC */ }

    tft.init();
    tft.setRotation(3);
    tft.fillScreen(TFT_BLACK);

    tft.setTextColor(TFT_WHITE, TFT_BLACK);
    tft.setTextSize(2);

    tft.setCursor(10, 10);
    tft.println("SoundBridge");

    tft.setCursor(10, 40);
    tft.println("A iniciar...");

    pinMode(PIN_BUTTON,   INPUT_PULLUP);
    pinMode(PIN_LED_DOT,  OUTPUT);
    pinMode(PIN_LED_DASH, OUTPUT);
    digitalWrite(PIN_LED_DOT,  LOW);
    digitalWrite(PIN_LED_DASH, LOW);

    // Brief startup blink
    digitalWrite(PIN_LED_DOT,  HIGH);
    digitalWrite(PIN_LED_DASH, HIGH);
    delay(300);
    digitalWrite(PIN_LED_DOT,  LOW);
    digitalWrite(PIN_LED_DASH, LOW);

    connectWiFi();
    sendSystemReady();
}

void loop() {
    // ── Morse input ──────────────────────────────────────────
    handleButton();
    handleInactivity();
    updateLeds();

    // ── Polling (non-blocking timer) ─────────────────────────
    if (millis() - lastPollMs >= POLL_INTERVAL_MS) {
        lastPollMs = millis();
        pollLatestMessage();
    }
}
