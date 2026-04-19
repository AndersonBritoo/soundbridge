/**
 * @file    morse.cpp
 * @path    firmware/esp32/src/morse.cpp
 * @brief   Classificação temporal de sinais Morse e emissão de eventos JSON via Serial.
 *
 * Recebe a duração de cada pressão do botão (de button.cpp), classifica-a como
 * ponto ou traço com base em DOT_THRESHOLD_MS, e emite o evento correspondente em
 * JSON pela porta série. Gere também os timers de inatividade que sinalizam fim de
 * letra e fim de palavra ao gateway externo.
 *
 * DESIGN: A comunicação é feita via Serial (JSON por linha) e não diretamente via
 * rede. Isto permite que o gateway externo — um processo separado com recursos
 * superiores — trate da decodificação Morse, persistência em base de dados e
 * exposição via API REST, sem sobrecarregar o microcontrolador.
 *
 * Este módulo é unidirecional: emite dados, nunca os recebe. A direção inversa
 * (receção de mensagens decodificadas) é responsabilidade de poller.cpp.
 *
 * Dependências: leds.h (feedback visual), config.h (limiares temporais)
 */

#include "morse.h"
#include "config.h"
#include "leds.h"
#include <Arduino.h>
#include <ArduinoJson.h>

// Instante (millis) da última libertação confirmada do botão.
// Valor 0 indica que ainda não ocorreu nenhuma pressão desde o arranque.
static uint32_t lastReleaseMs = 0;

// Flags de controlo que garantem que cada evento de fim-de-letra e fim-de-palavra
// é emitido no máximo uma vez por ciclo de inatividade (reiniciados em notifyRelease)
static bool     letterEndSent = false;
static bool     wordEndSent   = false;

void sendJson(JsonDocument& doc) {
    serializeJson(doc, Serial);
    // O newline é o delimitador de mensagem para o gateway que lê linha-a-linha
    Serial.println();
}

void sendSignal(const char* value) {
    JsonDocument doc;
    doc["type"]      = "signal";
    doc["value"]     = value;
    doc["timestamp"] = millis();
    sendJson(doc);
}

void sendEvent(const char* eventType) {
    JsonDocument doc;
    doc["type"]      = eventType;
    doc["timestamp"] = millis();
    sendJson(doc);
}

void sendSystemReady() {
    JsonDocument doc;
    doc["type"]      = "system";
    doc["message"]   = "ready";
    doc["timestamp"] = millis();
    sendJson(doc);
}

void classifyAndSend(uint32_t durationMs) {
    // Classifica a pressão comparando a duração com o limiar configurado.
    // Durações abaixo de DOT_THRESHOLD_MS são pontos; acima (ou iguais) são traços.
    if (durationMs < DOT_THRESHOLD_MS) {
        sendSignal(".");
        // COUPLING: acende o LED azul (PIN_LED_DOT) por LED_ON_MS milissegundos,
        // fornecendo confirmação visual imediata ao utilizador de que o sinal foi
        // registado como ponto.
        lightDotLed();
    } else {
        sendSignal("-");
        // COUPLING: acende o LED vermelho (PIN_LED_DASH) por LED_ON_MS milissegundos,
        // confirmando visualmente o registo do sinal como traço.
        lightDashLed();
    }
}

void notifyRelease() {
    // Regista o instante da libertação — a partir daqui handleInactivity() começa
    // a medir o silêncio para detetar fins de letra e de palavra.
    lastReleaseMs = millis();

    // Reinicia os flags para que os eventos de fim-de-letra e fim-de-palavra
    // possam ser emitidos novamente neste novo ciclo de inatividade.
    letterEndSent = false;
    wordEndSent   = false;
}

void handleInactivity() {
    // Guard: se ainda não ocorreu nenhuma pressão, não há inatividade a medir.
    if (lastReleaseMs == 0) return;

    uint32_t elapsed = millis() - lastReleaseMs;

    // Emite "letter_end" uma única vez quando o silêncio ultrapassa LETTER_END_MS.
    // O flag letterEndSent impede re-emissão enquanto o utilizador não pressionar
    // novamente o botão (o que chama notifyRelease e reinicia os flags).
    if (!letterEndSent && elapsed >= LETTER_END_MS) {
        sendEvent("letter_end");
        letterEndSent = true;
    }

    // Emite "word_end" uma única vez quando o silêncio ultrapassa WORD_END_MS.
    // WORD_END_MS > LETTER_END_MS garante que "letter_end" é sempre emitido
    // antes de "word_end" para a mesma pausa.
    if (!wordEndSent && elapsed >= WORD_END_MS) {
        sendEvent("word_end");
        wordEndSent = true;
    }
}