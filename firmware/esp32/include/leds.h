#pragma once
#include <Arduino.h>

void ledsInit();
void lightDotLed();
void lightDashLed();
void updateLeds();
void blinkBothLeds(int times, uint32_t onMs, uint32_t offMs);