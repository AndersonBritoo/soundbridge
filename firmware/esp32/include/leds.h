/**
 * @file    leds.h
 * @path    firmware/include/leds.h
 * @brief   Interface pública do módulo de feedback visual por LEDs.
 *
 * Expõe funções para acender individualmente cada LED de sinalização (ponto/traço)
 * por uma duração fixa e não-bloqueante, bem como uma função de blink bloqueante
 * usada em momentos de arranque e notificação de nova mensagem.
 *
 * O controlo temporal não-bloqueante de updateLeds() permite que o loop principal
 * continue a processar o botão e o poller enquanto os LEDs estão acesos.
 */

#pragma once
#include <Arduino.h>

/**
 * @brief   Configura os pinos dos LEDs como saídas digitais e garante estado inicial apagado.
 *
 * Deve ser chamada uma única vez em setup(), antes de qualquer outra função deste módulo.
 *
 * @note    Os pinos usados são PIN_LED_DOT e PIN_LED_DASH definidos em config.h.
 */
void ledsInit();

/**
 * @brief   Acende o LED de ponto (azul) por LED_ON_MS milissegundos de forma não-bloqueante.
 *
 * Regista o instante de acendimento internamente; updateLeds() trata do apagamento
 * quando o tempo expirar. Pode ser chamado mesmo que o LED já esteja aceso — o
 * timer é reiniciado.
 */
void lightDotLed();

/**
 * @brief   Acende o LED de traço (vermelho) por LED_ON_MS milissegundos de forma não-bloqueante.
 *
 * Comportamento análogo a lightDotLed(), aplicado ao LED do traço.
 */
void lightDashLed();

/**
 * @brief   Apaga os LEDs cujo tempo de acendimento (LED_ON_MS) já expirou.
 *
 * Deve ser chamada a cada iteração do loop(). Não bloqueia: apenas verifica
 * timestamps e escreve nos pinos se necessário. É o mecanismo que concretiza o
 * comportamento "não-bloqueante" prometido por lightDotLed() e lightDashLed().
 */
void updateLeds();

/**
 * @brief   Pisca ambos os LEDs simultaneamente um número definido de vezes — BLOQUEANTE.
 *
 * Usa delay() internamente, suspendendo o loop principal durante toda a sequência.
 *
 * @param   times  Número de vezes que os LEDs devem piscar.
 * @param   onMs   Duração do estado aceso em milissegundos.
 * @param   offMs  Duração do estado apagado entre blinks em milissegundos.
 *                 Ignorado após o último blink.
 *
 * @note    LIMITATION: Esta função é bloqueante. Durante a sua execução o botão
 *          não é lido, os timers de inatividade não avançam e o poller não corre.
 *          É aceitável em dois contextos: (1) no arranque (setup), onde o sistema
 *          ainda não está operacional; (2) na notificação de nova mensagem, onde
 *          a pausa breve (~600 ms para 2 blinks) é tolerável dado o intervalo de
 *          poll de 5 s.
 */
void blinkBothLeds(int times, uint32_t onMs, uint32_t offMs);