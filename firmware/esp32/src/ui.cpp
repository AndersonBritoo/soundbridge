/**
 * @file    ui.cpp
 * @path    firmware/esp32/src/ui.cpp
 * @brief   Interface gráfica no display TFT usando a biblioteca TFT_eSPI.
 *
 * Implementa a apresentação das mensagens Morse decodificadas num display ST7789
 * de 135×240 px. O ecrã divide-se em dois painéis verticais: texto decodificado
 * (topo) e sequência Morse original (base).
 *
 * DESIGN: A estratégia de refresh consiste em apagar o ecrã completo (fillScreen)
 * antes de cada redesenho. Esta abordagem é mais simples do que atualizar regiões
 * individuais e é adequada para este sistema porque drawUI() é chamada raramente
 * (a cada novo poll com mensagem nova, no máximo a cada POLL_INTERVAL_MS = 5 s),
 * tornando o flicker imperceptível.
 *
 * Dependências: TFT_eSPI (driver do display via SPI, configurado em platformio.ini)
 */

#include "ui.h"
#include <Arduino.h>
#include <TFT_eSPI.h>

// Instância do driver TFT — encapsulada neste módulo; nenhum outro módulo
// acede diretamente ao hardware do display.
static TFT_eSPI tft = TFT_eSPI();

void uiInit() {
    tft.init();

    // Rotação 3: landscape com o conector USB do ESP32 orientado para a esquerda,
    // correspondendo à montagem física no enclosure do projeto.
    tft.setRotation(3);

    tft.fillScreen(TFT_BLACK);
    tft.setTextColor(TFT_WHITE, TFT_BLACK);
    tft.setTextSize(2);
    tft.setCursor(10, 10);
    tft.println("SoundBridge");
    tft.setCursor(10, 40);
    tft.println("A iniciar...");
}

void drawUI(const char* text, const char* morse) {
    // Apaga o ecrã completo antes de redesenhar para evitar sobreposição de texto
    // de mensagens anteriores com conteúdo de comprimento diferente.
    tft.fillScreen(TFT_BLACK);

    // Bloco superior: texto decodificado
    tft.setTextColor(TFT_GREEN, TFT_BLACK);
    tft.setTextSize(2);
    tft.setCursor(10, 10);
    tft.println("Texto:");

    tft.setTextColor(TFT_WHITE, TFT_BLACK);
    tft.setCursor(10, 35);
    // Truncagem a 20 caracteres: com textSize=2 e largura útil de ~220 px,
    // cada caractere ocupa ~12 px, pelo que 20 chars preenchem a linha sem overflow.
    tft.println(String(text).substring(0, 20));

    // Bloco inferior: sequência Morse original
    tft.setTextColor(TFT_YELLOW, TFT_BLACK);
    tft.setTextSize(2);
    tft.setCursor(10, 80);
    tft.println("Morse:");

    tft.setCursor(10, 100);
    // Truncagem a 50 caracteres: a sequência Morse pode ser mais longa do que o
    // texto decodificado; 50 chars ocupam duas linhas visuais na área disponível
    // abaixo do rótulo "Morse:" sem sair do ecrã.
    tft.println(String(morse).substring(0, 50));
}