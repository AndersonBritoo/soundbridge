/**
 * @file    leds.cpp
 * @path    firmware/esp32/src/leds.cpp
 * @brief   Controlo dos LEDs de feedback visual com gestão temporal não-bloqueante.
 *
 * Os LEDs de ponto e traço são acesos durante LED_ON_MS milissegundos sempre que
 * um sinal Morse é classificado. O apagamento é gerido por updateLeds(), chamada
 * no loop principal, que verifica o tempo decorrido sem usar delay().
 *
 * O padrão de controlo temporal baseia-se em dois elementos por LED: um timestamp
 * de acendimento e um flag de estado ativo. Este padrão é comum em sistemas
 * embebidos sem RTOS para implementar temporizadores one-shot não-bloqueantes.
 *
 * Dependências: config.h (PIN_LED_DOT, PIN_LED_DASH, LED_ON_MS)
 */

#include "leds.h"
#include "config.h"
#include <Arduino.h>

// Timestamp (millis) do último acendimento de cada LED — usado para calcular
// quando o tempo de acendimento LED_ON_MS expirou.
static uint32_t dotLedOnMs   = 0;
static uint32_t dashLedOnMs  = 0;

// Flags que indicam se cada LED está atualmente aceso e necessita de ser monitorizado
// por updateLeds(). Evitam escritas desnecessárias no pino quando o LED já está apagado.
static bool     dotLedActive = false;
static bool     dashLedActive= false;

void ledsInit() {
    pinMode(PIN_LED_DOT,  OUTPUT);
    pinMode(PIN_LED_DASH, OUTPUT);
    // Garante estado apagado explícito no arranque — o estado de pinos GPIO
    // após reset não é garantido em todas as revisões de hardware do ESP32.
    digitalWrite(PIN_LED_DOT,  LOW);
    digitalWrite(PIN_LED_DASH, LOW);
}

void lightDotLed() {
    digitalWrite(PIN_LED_DOT, HIGH);
    // Regista o instante de acendimento para que updateLeds() possa calcular
    // a expiração sem bloquear o loop.
    dotLedOnMs   = millis();
    dotLedActive = true;
}

void lightDashLed() {
    digitalWrite(PIN_LED_DASH, HIGH);
    dashLedOnMs   = millis();
    dashLedActive = true;
}

void updateLeds() {
    uint32_t now = millis();

    // Para cada LED ativo, verifica se LED_ON_MS milissegundos já decorreram
    // desde o acendimento. Se sim, apaga o LED e desativa a monitorização.
    if (dotLedActive && (now - dotLedOnMs >= LED_ON_MS)) {
        digitalWrite(PIN_LED_DOT, LOW);
        dotLedActive = false;
    }
    if (dashLedActive && (now - dashLedOnMs >= LED_ON_MS)) {
        digitalWrite(PIN_LED_DASH, LOW);
        dashLedActive = false;
    }
}

void blinkBothLeds(int times, uint32_t onMs, uint32_t offMs) {
    // LIMITATION: Uso de delay() torna esta função bloqueante. O loop principal
    // é suspenso durante toda a sequência de blinks. Ver documentação em leds.h.
    for (int i = 0; i < times; i++) {
        digitalWrite(PIN_LED_DOT,  HIGH);
        digitalWrite(PIN_LED_DASH, HIGH);
        delay(onMs);
        digitalWrite(PIN_LED_DOT,  LOW);
        digitalWrite(PIN_LED_DASH, LOW);
        // O delay de separação não é aplicado após o último blink para evitar
        // uma pausa desnecessária no retorno ao loop principal.
        if (i < times - 1) delay(offMs);
    }
}