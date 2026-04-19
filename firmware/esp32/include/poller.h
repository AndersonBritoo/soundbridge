/**
 * @file    poller.h
 * @path    firmware/esp32/include/poller.h
 * @brief   Interface pública do módulo de polling periódico à API REST do gateway.
 *
 * Expõe uma única função de atualização que deve ser chamada no loop principal.
 * Internamente, o módulo faz pedidos HTTP GET ao endpoint /morse/latest a cada
 * POLL_INTERVAL_MS milissegundos e, quando existe uma mensagem nova, atualiza
 * o display TFT e aciona o feedback visual por LEDs.
 */

#pragma once

/**
 * @brief   Verifica se o intervalo de polling expirou e, se sim, consulta a API REST.
 *
 * Deve ser chamada a cada iteração do loop(). Usa millis() para controlo temporal
 * não-bloqueante entre polls. Quando o intervalo POLL_INTERVAL_MS (config.h) tiver
 * decorrido, executa um pedido HTTP GET síncrono ao endpoint configurado.
 *
 * A função só atualiza o display e os LEDs se a resposta contiver uma mensagem com
 * um id diferente do último processado (deduplicação por lastSeenId).
 *
 * @note    LIMITATION: O pedido HTTP é síncrono com timeout de 3 s. Durante este
 *          tempo o loop principal está bloqueado. Em condições normais de rede local
 *          o pedido completa em menos de 100 ms; o timeout de 3 s é o caso patológico.
 *
 * @note    COUPLING: Chama drawUI() de ui.h e blinkBothLeds() de leds.h quando
 *          uma mensagem nova é recebida.
 */
void pollerTick();