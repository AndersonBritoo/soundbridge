#include "ui.h"
#include <Arduino.h>
#include <TFT_eSPI.h>

static TFT_eSPI tft = TFT_eSPI();

void uiInit() {
    tft.init();
    tft.setRotation(3);
    tft.fillScreen(TFT_BLACK);
    tft.setTextColor(TFT_WHITE, TFT_BLACK);
    tft.setTextSize(2);
    tft.setCursor(10, 10);
    tft.println("SoundBridge");
    tft.setCursor(10, 40);
    tft.println("A iniciar...");
}

void drawUI(const char* text, const char* morse) {
    tft.fillScreen(TFT_BLACK);

    tft.setTextColor(TFT_GREEN, TFT_BLACK);
    tft.setTextSize(2);
    tft.setCursor(10, 10);
    tft.println("Texto:");

    tft.setTextColor(TFT_WHITE, TFT_BLACK);
    tft.setCursor(10, 35);
    tft.println(String(text).substring(0, 20));

    tft.setTextColor(TFT_YELLOW, TFT_BLACK);
    tft.setTextSize(2);
    tft.setCursor(10, 80);
    tft.println("Morse:");

    tft.setCursor(10, 100);
    tft.println(String(morse).substring(0, 50));
}