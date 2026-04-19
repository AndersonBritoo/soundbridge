#pragma once

/**
 * Blocks until the ESP32 is connected to the configured WiFi network.
 * Call once from setup().
 *
 * NOTE: This header is named soundbridge_wifi.h (not wifi.h) to avoid
 * a name collision with the ESP-IDF system header <wifi.h> that
 * PlatformIO resolves before local files.
 */
void connectWiFi();