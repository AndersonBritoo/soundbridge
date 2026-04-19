#include "poller.h"
#include "config.h"
#include "ui.h"
#include "leds.h"
#include <WiFi.h>
#include <Arduino.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

static uint32_t lastPollMs = 0;
static int      lastSeenId = -1;

static void pollLatestMessage() {
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("[poll] WiFi not connected - skipping.");
        return;
    }

    char url[128];
    snprintf(url, sizeof(url), "http://%s:%d/morse/latest", API_HOST, API_PORT);

    HTTPClient http;
    http.begin(url);
    http.setTimeout(3000);

    int httpCode = http.GET();
    if (httpCode != HTTP_CODE_OK) {
        Serial.printf("[poll] HTTP error: %d\n", httpCode);
        http.end();
        return;
    }

    String body = http.getString();
    http.end();

    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, body);
    if (err) {
        Serial.printf("[poll] JSON parse error: %s\n", err.c_str());
        return;
    }

    // ArduinoJson 7.x: use .is<T>() instead of containsKey()
    if (doc["status"].is<const char*>()) {
        Serial.println("[poll] No messages in database yet.");
        return;
    }

    int         id    = doc["id"]    | -1;
    const char* morse = doc["morse"] | "";
    const char* text  = doc["text"]  | "";

    if (id == lastSeenId) {
        Serial.printf("[poll] No new message (latest id=%d).\n", id);
        return;
    }

    lastSeenId = id;
    drawUI(text, morse);
    blinkBothLeds(2, 150, 150);
}

void pollerTick() {
    if (millis() - lastPollMs >= POLL_INTERVAL_MS) {
        lastPollMs = millis();
        pollLatestMessage();
    }
}