/**
 * @file    ui.h
 * @path    firmware/esp32/include/ui.h
 * @brief   Interface pública do módulo de interface gráfica no display TFT.
 *
 * Abstrai o hardware TFT_eSPI e expõe duas operações: inicialização do display
 * e redesenho completo com nova mensagem decodificada. A interface é intencionalmente
 * minimalista — o módulo não mantém estado de conteúdo; cada chamada a drawUI()
 * substitui completamente o ecrã anterior.
 */

#pragma once

/**
 * @brief   Inicializa o display TFT e apresenta o ecrã de arranque do SoundBridge.
 *
 * Configura a rotação, cor de fundo e tamanho de texto base, e exibe o nome do
 * sistema com uma mensagem de estado "A iniciar…". Deve ser chamada uma única vez
 * em setup(), preferencialmente antes de connectWiFi() para que o display forneça
 * feedback visual durante a ligação.
 *
 * @note    A rotação é fixada a 3 (landscape invertido) para corresponder à
 *          orientação física do display no enclosure do hardware.
 */
void uiInit();

/**
 * @brief   Redesenha o ecrã completo com o texto decodificado e a sequência Morse original.
 *
 * Apaga o ecrã (fillScreen preto) e renderiza dois blocos de texto:
 * — Linha superior: rótulo "Texto:" e os primeiros 20 caracteres de text (branco)
 * — Linha inferior: rótulo "Morse:" e os primeiros 50 caracteres de morse (amarelo)
 *
 * @param   text   String com o texto decodificado a apresentar (truncada a 20 chars).
 * @param   morse  String com a sequência Morse original (truncada a 50 chars).
 *
 * @note    A truncagem protege contra overflow de texto para fora da área útil do
 *          display físico (135×240 px com texto de tamanho 2).
 */
void drawUI(const char* text, const char* morse);