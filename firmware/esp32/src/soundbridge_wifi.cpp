/**
 * @file    soundbridge_wifi.cpp
 * @path    firmware/esp32/src/soundbridge_wifi.cpp
 * @brief   Ligação bloqueante à rede WiFi no arranque do firmware SoundBridge.
 *
 * Implementa uma ligação WiFi simples e robusta para o contexto de setup():
 * tenta ligar indefinidamente, imprimindo um ponto por cada 500 ms de espera,
 * e só retorna quando WL_CONNECTED for atingido.
 *
 * DESIGN: A abordagem bloqueante é preferível a uma ligação assíncrona em setup()
 * porque simplifica o código dos módulos dependentes (poller, morse) — estes podem
 * assumir que o WiFi está sempre disponível após o arranque, em vez de terem de
 * gerir um estado de "ligação pendente". A única exceção tratada é a desconexão
 * temporária durante operação, verificada como guard clause em poller.cpp.
 *
 * NOTE: O ficheiro chama-se soundbridge_wifi.cpp e não wifi.cpp para evitar
 * colisão de nomes com o header de sistema <wifi.h> do ESP-IDF. Ver soundbridge_wifi.h.
 *
 * Dependências: config.h (WIFI_SSID, WIFI_PASSWORD)
 */

#include "wifi.h"
#include "config.h"
#include <WiFi.h>
#include <Arduino.h>

void connectWiFi() {
    Serial.printf("[WiFi] Connecting to %s", WIFI_SSID);

    // Modo station: o ESP32 é um cliente da rede, não um access point
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    // Loop de espera bloqueante: imprime um ponto a cada 500 ms para indicar
    // progresso via Serial. O Watchdog do ESP32 é alimentado implicitamente
    // pelo delay() interno do SDK, pelo que não ocorre reset por timeout.
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }

    // Confirmação com o IP atribuído por DHCP — útil para verificar que o
    // dispositivo está acessível na rede antes de iniciar o polling à API.
    Serial.printf("\n[WiFi] Connected. IP: %s\n",
                  WiFi.localIP().toString().c_str());
}