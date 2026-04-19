#pragma once

// ════════════════════════════════════════════════════════════
//  SoundBridge – Central Configuration
// ════════════════════════════════════════════════════════════

// ── WiFi ─────────────────────────────────────────────────────
#define WIFI_SSID        "NOWO-2ECA4"
#define WIFI_PASSWORD    "64Sw3kccmWmT"

// ── API Server ───────────────────────────────────────────────
#define API_HOST         "192.168.0.16"
#define API_PORT         8000
#define POLL_INTERVAL_MS 5000UL

// ── Pin Definitions ──────────────────────────────────────────
#define PIN_BUTTON       5
#define PIN_LED_DOT      12   // blue  – dot
#define PIN_LED_DASH     13   // red   – dash

// ── Morse Timing (ms) ────────────────────────────────────────
#define DEBOUNCE_MS      50UL
#define DOT_THRESHOLD_MS 300UL
#define LED_ON_MS        200UL
#define LETTER_END_MS    1000UL
#define WORD_END_MS      2500UL