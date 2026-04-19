/**
 * @file    button.h
 * @path    firmware/esp32/include/button.h
 * @brief   Interface pública do módulo de leitura do botão físico com debounce por FSM.
 *
 * Expõe apenas duas funções: inicialização do pino e atualização periódica da
 * máquina de estados. Toda a lógica de debounce e o estado interno são
 * encapsulados em button.cpp e invisíveis ao resto do sistema.
 */

#pragma once
#include <Arduino.h>

/**
 * @brief   Configura o pino do botão como entrada com resistência de pull-up interna.
 *
 * Deve ser chamada uma única vez em setup(), antes de qualquer invocação de
 * handleButton(). Após esta chamada, o nível lógico em repouso do pino é HIGH;
 * uma pressão física puxa o pino a LOW.
 *
 * @note    O pino usado é definido por PIN_BUTTON em config.h.
 */
void buttonInit();

/**
 * @brief   Atualiza a FSM de debounce do botão — deve ser chamada a cada iteração do loop.
 *
 * Lê o estado raw do pino, avança a máquina de estados e, quando uma pressão
 * válida (debounced) é detetada, invoca classifyAndSend() (morse.h) com a
 * duração da pressão em milissegundos.
 *
 * Não bloqueia: toda a gestão temporal usa millis() e retorna imediatamente.
 *
 * @note    COUPLING: Chama notifyRelease() e classifyAndSend() definidas em morse.h
 *          para reportar eventos de pressão ao módulo Morse.
 */
void handleButton();