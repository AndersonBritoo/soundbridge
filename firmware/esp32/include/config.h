/**
 * @file    config.h
 * @path    firmware/esp32/include/config.h
 * @brief   Ponto único de configuração de todo o firmware SoundBridge.
 *
 * Centraliza todas as constantes de compilação do sistema: credenciais de rede,
 * endereço da API, pinos de hardware e limiares temporais do protocolo Morse.
 * Alterar qualquer parâmetro operacional do sistema deve ser feito exclusivamente
 * aqui — nenhum módulo deve ter "magic numbers" hardcoded.
 *
 * DESIGN: A centralização em config.h evita divergências entre módulos e
 * facilita a adaptação do firmware a hardware ou infraestrutura diferentes
 * sem tocar na lógica de negócio.
 */

#pragma once

// ════════════════════════════════════════════════════════════
//  SoundBridge – Central Configuration
// ════════════════════════════════════════════════════════════

// ── WiFi ─────────────────────────────────────────────────────
#define WIFI_SSID        "NOWO-2ECA4"       // SSID da rede WiFi à qual o ESP32 se liga
#define WIFI_PASSWORD    "64Sw3kccmWmT"     // Palavra-passe da rede WiFi

// ── API Server ───────────────────────────────────────────────
#define API_HOST         "192.168.0.107"     // Endereço IP do gateway/servidor REST na rede local
#define API_PORT         8000               // Porto TCP onde o servidor REST escuta pedidos HTTP
#define POLL_INTERVAL_MS 5000UL             // Intervalo entre polls à API (ms). 5 s é suficiente
                                            // para feedback não-crítico e reduz carga na rede.

// ── Pin Definitions ──────────────────────────────────────────
#define PIN_BUTTON       5                  // GPIO do botão físico (lido com INPUT_PULLUP; LOW = premido)
#define PIN_LED_DOT      12                 // GPIO do LED azul — acende quando o sinal classificado é ponto (.)
#define PIN_LED_DASH     13                 // GPIO do LED vermelho — acende quando o sinal classificado é traço (-)

// ── Morse Timing (ms) ────────────────────────────────────────
#define DEBOUNCE_MS      50UL               // Janela de debounce na libertação do botão (ms).
                                            // 50 ms filtra o ressalto mecânico típico de
                                            // tactile switches sem introduzir latência perceptível.

#define DOT_THRESHOLD_MS 300UL              // Duração máxima de uma pressão para ser classificada
                                            // como ponto (ms). Pressões >= 300 ms são traços.
                                            // Valor baseado na convenção ITU-R M.1677 adaptada
                                            // para utilizadores não-experientes.

#define LED_ON_MS        200UL              // Duração de acendimento dos LEDs de feedback (ms).
                                            // Tempo suficientemente longo para ser visível mas
                                            // inferior a DOT_THRESHOLD_MS para não mascarar
                                            // sinais consecutivos rápidos.

#define LETTER_END_MS    1000UL             // Silêncio após a última pressão para considerar
                                            // a letra completa (ms). Equivale a 3× um ponto
                                            // na cadência padrão Morse.

#define WORD_END_MS      2500UL             // Silêncio após a última pressão para considerar
                                            // a palavra completa (ms). Equivale a 7× um ponto
                                            // na cadência padrão Morse, aqui relaxado para
                                            // utilizadores iniciantes.