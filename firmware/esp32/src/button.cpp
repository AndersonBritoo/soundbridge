/**
 * @file    button.cpp
 * @path    firmware/esp32/src/button.cpp
 * @brief   Leitura do botão físico com debounce implementado por máquina de estados finitos (FSM).
 *
 * O debounce é aplicado exclusivamente na fase de libertação do botão, não na
 * pressão. Esta assimetria é intencional: queremos registar o instante de pressão
 * imediatamente (para iniciar a medição da duração), mas só confirmar a libertação
 * após estabilização elétrica do sinal.
 *
 * A duração da pressão — medida entre o flanco descendente detetado e o fim do
 * período de debounce — é passada ao módulo Morse para classificação como ponto
 * ou traço. Toda a gestão temporal usa millis(), sem interrupções de hardware.
 *
 * Dependências: morse.h (notifyRelease, classifyAndSend), config.h (DEBOUNCE_MS, PIN_BUTTON)
 */

#include "button.h"
#include "config.h"
#include "morse.h"
#include <Arduino.h>

/**
 * Estados internos da FSM do botão.
 *
 * IDLE               — Botão em repouso; à espera de um flanco descendente.
 * PRESSED            — Botão confirmado como premido; a medir a duração da pressão.
 * DEBOUNCING_RELEASE — Botão aparentemente libertado; a aguardar estabilização do sinal
 *                      antes de confirmar a libertação e calcular a duração.
 */
enum class ButtonState { IDLE, PRESSED, DEBOUNCING_RELEASE };

// Estado atual da FSM — inicializado em IDLE (botão em repouso)
static ButtonState buttonState     = ButtonState::IDLE;

// Instante (millis) em que o flanco descendente foi detetado — base de medição da duração
static uint32_t    pressStartMs    = 0;

// Instante (millis) em que se iniciou o período de debounce da libertação
static uint32_t    debounceStartMs = 0;

// Último valor raw lido do pino — usado para deteção de flanco (transição HIGH→LOW)
static bool        lastRawButton   = HIGH;

void buttonInit() {
    pinMode(PIN_BUTTON, INPUT_PULLUP);
}

void handleButton() {
    bool     rawButton = digitalRead(PIN_BUTTON);
    uint32_t now       = millis();

    switch (buttonState) {

        case ButtonState::IDLE:
            // Deteção de flanco descendente: o pino transitou de HIGH (repouso) para LOW (premido).
            // Comparar rawButton com lastRawButton em vez de apenas verificar rawButton == LOW
            // evita que uma pressão contínua seja re-detetada a cada iteração.
            if (rawButton == LOW && lastRawButton == HIGH) {
                debounceStartMs = now;
                buttonState     = ButtonState::PRESSED;
                pressStartMs    = now;  // Inicia a medição da duração neste instante exato
            }
            break;

        case ButtonState::PRESSED:
            // O botão foi libertado (pino voltou a HIGH). Não se confirma ainda a libertação
            // porque o sinal pode estar a ressaltar. Inicia-se o período de debounce.
            if (rawButton == HIGH) {
                debounceStartMs = now;
                buttonState     = ButtonState::DEBOUNCING_RELEASE;
            }
            break;

        case ButtonState::DEBOUNCING_RELEASE:
            if (rawButton == LOW) {
                // O pino voltou a LOW durante o período de debounce — foi um ressalto mecânico,
                // não uma libertação real. Regressa ao estado PRESSED e continua a medir.
                buttonState = ButtonState::PRESSED;
            } else if (now - debounceStartMs >= DEBOUNCE_MS) {
                // O pino manteve-se HIGH durante DEBOUNCE_MS: libertação confirmada.
                // Calcula a duração total da pressão e delega a classificação ao módulo Morse.
                uint32_t duration = now - pressStartMs;

                // COUPLING: notifyRelease() reinicia os timers de inatividade em morse.cpp,
                // garantindo que o relógio de fim-de-letra/palavra começa a contar a partir
                // deste momento.
                notifyRelease();

                // COUPLING: classifyAndSend() em morse.cpp decide se a duração corresponde
                // a um ponto ou traço, emite o evento JSON via Serial e acende o LED adequado.
                classifyAndSend(duration);

                buttonState = ButtonState::IDLE;
            }
            break;
    }

    // Guarda o estado raw atual para comparação na próxima iteração (deteção de flancos)
    lastRawButton = rawButton;
}