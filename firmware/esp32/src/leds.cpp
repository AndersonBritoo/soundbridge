#include "leds.h"
#include "config.h"
#include <Arduino.h>

static uint32_t dotLedOnMs   = 0;
static uint32_t dashLedOnMs  = 0;
static bool     dotLedActive = false;
static bool     dashLedActive= false;

void ledsInit() {
    pinMode(PIN_LED_DOT,  OUTPUT);
    pinMode(PIN_LED_DASH, OUTPUT);
    digitalWrite(PIN_LED_DOT,  LOW);
    digitalWrite(PIN_LED_DASH, LOW);
}

void lightDotLed() {
    digitalWrite(PIN_LED_DOT, HIGH);
    dotLedOnMs   = millis();
    dotLedActive = true;
}

void lightDashLed() {
    digitalWrite(PIN_LED_DASH, HIGH);
    dashLedOnMs   = millis();
    dashLedActive = true;
}

void updateLeds() {
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

void blinkBothLeds(int times, uint32_t onMs, uint32_t offMs) {
    for (int i = 0; i < times; i++) {
        digitalWrite(PIN_LED_DOT,  HIGH);
        digitalWrite(PIN_LED_DASH, HIGH);
        delay(onMs);
        digitalWrite(PIN_LED_DOT,  LOW);
        digitalWrite(PIN_LED_DASH, LOW);
        if (i < times - 1) delay(offMs);
    }
}