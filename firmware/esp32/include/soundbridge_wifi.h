/**
 * @file    soundbridge_wifi.h
 * @path    firmware/esp32/include/soundbridge_wifi.h
 * @brief   Interface pública do módulo de ligação WiFi bloqueante no arranque.
 *
 * NOTE: Este ficheiro chama-se soundbridge_wifi.h e não wifi.h para evitar uma
 * colisão de nomes com o header de sistema <wifi.h> do ESP-IDF, que o PlatformIO
 * resolve com prioridade sobre ficheiros locais quando os nomes coincidem.
 */

#pragma once

/**
 * @brief   Estabelece ligação à rede WiFi configurada em config.h — BLOQUEANTE.
 *
 * Configura o ESP32 em modo station (WIFI_STA), inicia a ligação com as
 * credenciais WIFI_SSID/WIFI_PASSWORD e aguarda em loop até WL_CONNECTED.
 * Imprime o progresso e o IP atribuído via Serial.
 *
 * Deve ser chamada uma única vez em setup(), após a inicialização da porta série
 * e do display, para que exista feedback visual e de diagnóstico durante a espera.
 *
 * @note    DESIGN: O comportamento bloqueante é intencional e adequado ao contexto
 *          de setup(). Sem ligação WiFi o firmware não tem utilidade operacional
 *          (não pode fazer polling à API), pelo que não faz sentido continuar a
 *          inicialização se a ligação falhar. Um timeout com reboot por Watchdog
 *          seria uma evolução futura válida.
 */
void connectWiFi();