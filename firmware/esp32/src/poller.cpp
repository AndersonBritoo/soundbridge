/**
 * @file    poller.cpp
 * @path    firmware/esp32/src/poller.cpp
 * @brief   Cliente HTTP periódico para polling da API REST do gateway SoundBridge.
 *
 * A cada POLL_INTERVAL_MS milissegundos, faz um GET a http://<API_HOST>:<API_PORT>/morse/latest
 * e interpreta a resposta JSON. Se o campo "id" for diferente do último visto,
 * a mensagem é nova e o display é atualizado. Caso contrário, o pedido é silenciosamente
 * descartado.
 *
 * O formato esperado da resposta JSON da API é:
 *   { "id": <int>, "morse": "<string>", "text": "<string>" }
 * Quando não há mensagens na base de dados, o gateway responde com um objeto que
 * contém um campo "status" (string), sem os campos "id", "morse", "text".
 *
 * DESIGN: O polling é preferível a WebSockets ou SSE porque simplifica tanto o
 * firmware (sem gestão de conexão persistente) como o gateway, e a latência de
 * 5 s é aceitável para este caso de uso.
 *
 * Dependências: ui.h (drawUI), leds.h (blinkBothLeds), config.h (API_HOST, API_PORT,
 *               POLL_INTERVAL_MS)
 */

#include "poller.h"
#include "config.h"
#include "ui.h"
#include "leds.h"
#include <WiFi.h>
#include <Arduino.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// Timestamp (millis) do último poll executado — controla o intervalo entre pedidos
static uint32_t lastPollMs = 0;

// ID da última mensagem processada — mecanismo de deduplicação que evita redesenhar
// o display com a mesma mensagem a cada intervalo de polling
static int      lastSeenId = -1;

/**
 * @brief   Executa um único pedido HTTP GET ao endpoint /morse/latest e processa a resposta.
 *
 * Função interna (não exposta no header). Trata dos casos de erro (WiFi desligado,
 * HTTP != 200, JSON inválido, ausência de mensagens) de forma defensiva, sem
 * propagar exceções nem travar o sistema.
 */
static void pollLatestMessage() {
    // Guard clause: se o WiFi não estiver ligado, ignora o poll sem erro fatal.
    // Pode ocorrer após uma desconexão temporária — o sistema recupera
    // automaticamente no ciclo seguinte se a ligação for restabelecida.
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("[poll] WiFi not connected - skipping.");
        return;
    }

    char url[128];
    snprintf(url, sizeof(url), "http://%s:%d/morse/latest", API_HOST, API_PORT);

    HTTPClient http;
    http.begin(url);

    // Timeout de 3 s: limita o bloqueio do loop principal em caso de servidor
    // lento ou rede congestionada. Ver LIMITATION em poller.h.
    http.setTimeout(3000);

    int httpCode = http.GET();
    if (httpCode != HTTP_CODE_OK) {
        Serial.printf("[poll] HTTP error: %d\n", httpCode);
        http.end();
        return;
    }

    String body = http.getString();
    http.end();

    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, body);
    if (err) {
        Serial.printf("[poll] JSON parse error: %s\n", err.c_str());
        return;
    }

    // Deteção de resposta "sem mensagens": o gateway retorna um objeto com campo
    // "status" (string) quando a base de dados está vazia. ArduinoJson 7.x usa
    // .is<T>() em vez do depreciado containsKey() para verificar tipo e presença.
    if (doc["status"].is<const char*>()) {
        Serial.println("[poll] No messages in database yet.");
        return;
    }

    int         id    = doc["id"]    | -1;
    const char* morse = doc["morse"] | "";
    const char* text  = doc["text"]  | "";

    // Deduplicação: compara o id da resposta com o último processado.
    // Evita redesenhos desnecessários do display e blinks repetidos quando
    // não existem mensagens novas desde o último poll.
    if (id == lastSeenId) {
        Serial.printf("[poll] No new message (latest id=%d).\n", id);
        return;
    }

    // Mensagem nova: atualiza o display e fornece feedback visual ao utilizador.
    lastSeenId = id;

    // COUPLING: drawUI() em ui.h redesenha o ecrã TFT com o novo conteúdo
    drawUI(text, morse);

    // COUPLING: blinkBothLeds() em leds.h sinaliza visualmente a chegada de nova
    // mensagem. Bloqueante por ~600 ms (2 × (150 ms on + 150 ms off)) — aceitável
    // dado que a mensagem já foi recebida e o próximo poll só ocorre em 5 s.
    blinkBothLeds(2, 150, 150);
}

void pollerTick() {
    // Controlo temporal não-bloqueante: só executa o pedido HTTP quando o intervalo
    // POLL_INTERVAL_MS tiver decorrido desde o último poll.
    if (millis() - lastPollMs >= POLL_INTERVAL_MS) {
        lastPollMs = millis();
        pollLatestMessage();
    }
}