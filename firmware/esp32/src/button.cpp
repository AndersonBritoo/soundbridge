#include "button.h"
#include "config.h"
#include "morse.h"
#include <Arduino.h>

enum class ButtonState { IDLE, PRESSED, DEBOUNCING_RELEASE };

static ButtonState buttonState     = ButtonState::IDLE;
static uint32_t    pressStartMs    = 0;
static uint32_t    debounceStartMs = 0;
static bool        lastRawButton   = HIGH;

void buttonInit() {
    pinMode(PIN_BUTTON, INPUT_PULLUP);
}

void handleButton() {
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
                notifyRelease();
                classifyAndSend(duration);
                buttonState = ButtonState::IDLE;
            }
            break;
    }

    lastRawButton = rawButton;
}