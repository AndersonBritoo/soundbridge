/**
 * @file    morse.h
 * @path    firmware/esp32/include/morse.h
 * @brief   Interface pública do módulo de classificação Morse e emissão de eventos JSON via Serial.
 *
 * Este módulo é responsável por toda a comunicação de saída do firmware: classifica
 * a duração de pressões como pontos ou traços, deteta limites de letra e palavra por
 * inatividade temporal, e serializa todos os eventos em JSON para o gateway externo.
 *
 * DESIGN: Os dados são emitidos via Serial (USB) em vez de diretamente para a rede.
 * Esta separação desacopla o firmware do transporte de rede e permite que um gateway
 * externo (Python, Node, etc.) trate do encaminhamento, persistência e decodificação
 * Morse sem sobrecarregar o ESP32.
 *
 * Este módulo é assimétrico por design: envia dados, nunca os recebe. A receção
 * de mensagens decodificadas é responsabilidade exclusiva de poller.cpp.
 */

#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>

/**
 * @brief   Serializa um documento JSON para a porta Serial seguido de newline.
 *
 * Função de transporte de baixo nível usada pelos restantes emissores deste módulo.
 * O gateway externo lê linha-a-linha, pelo que o newline é o delimitador de mensagem.
 *
 * @param   doc  Documento ArduinoJson já preenchido a serializar.
 *
 * @note    Escreve diretamente em Serial — não usar em contextos onde a porta
 *          série não esteja inicializada.
 */
void sendJson(JsonDocument& doc);

/**
 * @brief   Emite um evento de sinal Morse {"type":"signal","value":"."/"-","timestamp":…}.
 *
 * Chamada após a classificação de uma pressão como ponto ou traço.
 *
 * @param   value  Cadeia de caracteres com o símbolo Morse: "." ou "-".
 */
void sendSignal(const char* value);

/**
 * @brief   Emite um evento temporal genérico {"type":<eventType>,"timestamp":…}.
 *
 * Usada para emitir "letter_end" e "word_end" quando os limiares de inatividade
 * definidos em config.h são atingidos.
 *
 * @param   eventType  Nome do evento (ex: "letter_end", "word_end").
 */
void sendEvent(const char* eventType);

/**
 * @brief   Emite o evento de handshake {"type":"system","message":"ready","timestamp":…}.
 *
 * Deve ser chamada uma única vez no final de setup(), após a ligação WiFi estar
 * estabelecida. Sinaliza ao gateway externo que o firmware completou a inicialização
 * e está pronto a receber sinais do botão.
 */
void sendSystemReady();

/**
 * @brief   Classifica a duração de uma pressão como ponto ou traço e emite o evento correspondente.
 *
 * Compara durationMs com DOT_THRESHOLD_MS (config.h): pressões mais curtas são pontos,
 * iguais ou mais longas são traços. Além de emitir o evento JSON, acende o LED de
 * feedback adequado via leds.h.
 *
 * @param   durationMs  Duração da pressão do botão em milissegundos.
 *
 * @note    COUPLING: Chama lightDotLed() ou lightDashLed() de leds.h para feedback visual imediato.
 */
void classifyAndSend(uint32_t durationMs);

/**
 * @brief   Regista o instante de libertação do botão e reinicia os flags de inatividade.
 *
 * Deve ser chamada imediatamente após cada libertação confirmada do botão (por button.cpp).
 * Reinicia o estado interno de forma a que handleInactivity() comece a contar o silêncio
 * a partir do instante correto.
 *
 * @note    Não emite nenhum evento — apenas atualiza o estado interno do módulo.
 */
void notifyRelease();

/**
 * @brief   Verifica se os limiares de inatividade foram atingidos e emite os eventos de controlo.
 *
 * Deve ser chamada a cada iteração do loop(). Compara o tempo decorrido desde a última
 * libertação com LETTER_END_MS e WORD_END_MS (config.h). Cada evento ("letter_end",
 * "word_end") é emitido no máximo uma vez por pressão, graças aos flags internos
 * letterEndSent e wordEndSent.
 *
 * Não faz nada se nenhuma pressão tiver ocorrido ainda (lastReleaseMs == 0).
 */
void handleInactivity();