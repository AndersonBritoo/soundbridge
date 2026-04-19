#include "morse.h"
#include "config.h"
#include "leds.h"
#include <Arduino.h>
#include <ArduinoJson.h>

static uint32_t lastReleaseMs = 0;
static bool     letterEndSent = false;
static bool     wordEndSent   = false;

void sendJson(JsonDocument& doc) {
    serializeJson(doc, Serial);
    Serial.println();
}

void sendSignal(const char* value) {
    JsonDocument doc;
    doc["type"]      = "signal";
    doc["value"]     = value;
    doc["timestamp"] = millis();
    sendJson(doc);
}

void sendEvent(const char* eventType) {
    JsonDocument doc;
    doc["type"]      = eventType;
    doc["timestamp"] = millis();
    sendJson(doc);
}

void sendSystemReady() {
    JsonDocument doc;
    doc["type"]      = "system";
    doc["message"]   = "ready";
    doc["timestamp"] = millis();
    sendJson(doc);
}

void classifyAndSend(uint32_t durationMs) {
    if (durationMs < DOT_THRESHOLD_MS) {
        sendSignal(".");
        lightDotLed();
    } else {
        sendSignal("-");
        lightDashLed();
    }
}

void notifyRelease() {
    lastReleaseMs = millis();
    letterEndSent = false;
    wordEndSent   = false;
}

void handleInactivity() {
    if (lastReleaseMs == 0) return;
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