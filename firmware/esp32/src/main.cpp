/**
 * @file    main.cpp
 * @path    firmware/esp32/src/main.cpp
 * @brief   Orquestrador principal do firmware SoundBridge — ponto de entrada do PlatformIO.
 *
 * Este ficheiro não contém qualquer lógica de negócio. O seu único papel é
 * inicializar os módulos pela ordem correta em setup() e invocar as suas
 * funções de atualização no loop principal. Toda a lógica reside nos módulos
 * dedicados (button, morse, leds, ui, poller, soundbridge_wifi).
 *
 * DESIGN: A arquitetura é baseada em polling cooperativo — não é usado RTOS
 * nem interrupções de hardware. Cada módulo expõe uma função "tick" ou "handle"
 * que deve ser chamada periodicamente no loop(). Esta abordagem é adequada para
 * este sistema porque as latências toleráveis são na ordem das dezenas de
 * milissegundos e a complexidade não justifica o overhead de um RTOS.
 *
 * NOTE: Em PlatformIO o ponto de entrada deve ser main.cpp e não main.ino,
 * pois o framework Arduino é invocado diretamente pelo linker sem o pré-
 * processador do IDE Arduino.
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
    // Inicializa a porta série a 115200 baud para emissão de eventos JSON
    // e logs de diagnóstico. O loop de espera garante que a ligação USB CDC
    // está estabelecida antes de qualquer output — relevante em desenvolvimento.
    Serial.begin(115200);
    while (!Serial) { /* wait for USB CDC */ }

    // Inicializa o display TFT e apresenta o ecrã de arranque
    uiInit();

    // Configura os pinos dos LEDs e executa um blink de confirmação de arranque
    ledsInit();
    blinkBothLeds(1, 300, 0);   // startup blink

    // Configura o pino do botão com INPUT_PULLUP e prepara a FSM interna
    buttonInit();

    // Estabelece ligação WiFi — bloqueante por design (ver soundbridge_wifi.cpp)
    connectWiFi();

    // Envia o evento de handshake {"type":"system","message":"ready"} via Serial
    // para sinalizar ao gateway externo que o firmware está operacional
    sendSystemReady();
}

void loop() {
    // DESIGN: Polling cooperativo — cada função corre até terminar e cede o
    // controlo. Não há preempção. A latência máxima de cada ciclo é determinada
    // pela função mais lenta (tipicamente pollerTick com o timeout HTTP de 3 s).

    // Lê o botão físico e avança a FSM de debounce/classificação
    handleButton();

    // Verifica se o silêncio após a última pressão atingiu os limiares de
    // fim-de-letra ou fim-de-palavra e emite os eventos JSON correspondentes
    handleInactivity();

    // Apaga os LEDs cujo tempo de acendimento expirou (operação não-bloqueante)
    updateLeds();

    // Executa um poll à API REST se o intervalo configurado tiver decorrido
    pollerTick();
}