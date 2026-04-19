/*
 * SoundBridge – main.cpp
 *
 * PlatformIO entry point. Thin orchestrator only –
 * all logic lives in the dedicated modules.
 *
 * NOTE: On PlatformIO the file must be main.cpp, not main.ino.
 */

#include <Arduino.h>
#include "config.h"
#include "soundbridge_wifi.h"
#include "ui.h"
#include "leds.h"
#include "button.h"
#include "morse.h"
#include "poller.h"

void setup() {
    Serial.begin(115200);
    while (!Serial) { /* wait for USB CDC */ }

    uiInit();

    ledsInit();
    blinkBothLeds(1, 300, 0);   // startup blink

    buttonInit();

    connectWiFi();
    sendSystemReady();
}

void loop() {
    handleButton();
    handleInactivity();
    updateLeds();
    pollerTick();
}