#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>

void sendJson(JsonDocument& doc);
void sendSignal(const char* value);
void sendEvent(const char* eventType);
void sendSystemReady();
void classifyAndSend(uint32_t durationMs);
void handleInactivity();
void notifyRelease();