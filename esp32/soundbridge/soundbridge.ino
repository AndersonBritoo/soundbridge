/*
 * SoundBridge - ESP32 Firmware
 * Sistema de captura de sinais Morse
 * 
 * Hardware:
 * - Botão: GPIO 5 (INPUT_PULLUP)
 * - LED Ponto (Azul): GPIO 12
 * - LED Traço (Vermelho): GPIO 13
 * 
 * Protocolo:
 * JSON simples via Serial (115200 baud)
 * {"signal":"."} ou {"signal":"-"}
 * {"event":"letter_end"} ou {"event":"word_end"}
 */

#include <ArduinoJson.h>

// ==================== PINOS ====================
#define PIN_BOTAO 5
#define PIN_LED_PONTO 12
#define PIN_LED_TRACO 13

// ==================== CONSTANTES ====================
const unsigned long DEBOUNCE = 50;           // ms
const unsigned long THRESHOLD = 300;         // ms - Ponto vs Traço
const unsigned long TIMEOUT_LETRA = 1000;    // ms - Separação de letras
const unsigned long TIMEOUT_PALAVRA = 2500;  // ms - Separação de palavras
const unsigned long LED_DURATION = 200;      // ms - Feedback visual

// ==================== VARIÁVEIS ====================
bool botaoEstado = HIGH;
bool botaoAnterior = HIGH;
unsigned long tempoMudanca = 0;

bool pressionado = false;
unsigned long tempoPressao = 0;

unsigned long tempoLED = 0;
bool ledAtivo = false;

unsigned long tempoUltimoSinal = 0;
bool aguardandoLetra = false;
bool aguardandoPalavra = false;

StaticJsonDocument<100> doc;

// ==================== SETUP ====================
void setup() {
  Serial.begin(115200);
  
  pinMode(PIN_BOTAO, INPUT_PULLUP);
  pinMode(PIN_LED_PONTO, OUTPUT);
  pinMode(PIN_LED_TRACO, OUTPUT);
  
  digitalWrite(PIN_LED_PONTO, LOW);
  digitalWrite(PIN_LED_TRACO, LOW);
  
  // Teste de LEDs
  digitalWrite(PIN_LED_PONTO, HIGH);
  delay(300);
  digitalWrite(PIN_LED_PONTO, LOW);
  delay(200);
  digitalWrite(PIN_LED_TRACO, HIGH);
  delay(300);
  digitalWrite(PIN_LED_TRACO, LOW);
  
  enviarMensagem("system", "ready");

  enviarMensagem("system", "reset");
}

// ==================== LOOP ====================
void loop() {
  lerBotao();
  gerirLED();
  processarTimeouts();
  delay(10);
}

// ==================== LER BOTÃO ====================
void lerBotao() {
  bool leitura = digitalRead(PIN_BOTAO);
  
  // Debounce
  if (leitura != botaoAnterior) {
    tempoMudanca = millis();
  }
  
  if ((millis() - tempoMudanca) > DEBOUNCE) {
    if (leitura != botaoEstado) {
      botaoEstado = leitura;
      
      if (botaoEstado == LOW && !pressionado) {
        // Botão pressionado
        pressionado = true;
        tempoPressao = millis();
      }
      
      if (botaoEstado == HIGH && pressionado) {
        // Botão libertado
        pressionado = false;
        unsigned long duracao = millis() - tempoPressao;
        
        if (duracao < THRESHOLD) {
          // PONTO
          ativarLED(PIN_LED_PONTO);
          enviarSinal(".");
        } else {
          // TRAÇO
          ativarLED(PIN_LED_TRACO);
          enviarSinal("-");
        }
        
        tempoUltimoSinal = millis();
        aguardandoLetra = true;
        aguardandoPalavra = true;
      }
    }
  }
  
  botaoAnterior = leitura;
}

// ==================== GERIR LED ====================
void gerirLED() {
  if (ledAtivo && (millis() - tempoLED) >= LED_DURATION) {
    digitalWrite(PIN_LED_PONTO, LOW);
    digitalWrite(PIN_LED_TRACO, LOW);
    ledAtivo = false;
  }
}

// ==================== PROCESSAR TIMEOUTS ====================
void processarTimeouts() {
  if (!aguardandoLetra && !aguardandoPalavra) {
    return;
  }
  
  unsigned long decorrido = millis() - tempoUltimoSinal;
  
  // Palavra (prioritário)
  if (aguardandoPalavra && decorrido >= TIMEOUT_PALAVRA) {
    enviarEvento("word_end");
    aguardandoPalavra = false;
    aguardandoLetra = false;
    return;
  }
  
  // Letra
  if (aguardandoLetra && decorrido >= TIMEOUT_LETRA) {
    enviarEvento("letter_end");
    aguardandoLetra = false;
  }
}

// ==================== ATIVAR LED ====================
void ativarLED(int pino) {
  digitalWrite(PIN_LED_PONTO, pino == PIN_LED_PONTO ? HIGH : LOW);
  digitalWrite(PIN_LED_TRACO, pino == PIN_LED_TRACO ? HIGH : LOW);
  ledAtivo = true;
  tempoLED = millis();
}

// ==================== ENVIAR SINAL ====================
void enviarSinal(const char* sinal) {
  doc.clear();
  doc["type"] = "signal";
  doc["value"] = sinal;
  doc["timestamp"] = millis();
  serializeJson(doc, Serial);
  Serial.println();
}

// ==================== ENVIAR EVENTO ====================
void enviarEvento(const char* evento) {
  doc.clear();
  doc["type"] = "event";
  doc["value"] = evento;
  doc["timestamp"] = millis();
  serializeJson(doc, Serial);
  Serial.println();
}

// ==================== ENVIAR MENSAGEM ====================
void enviarMensagem(const char* tipo, const char* msg) {
  doc.clear();
  doc["type"] = tipo;
  doc["message"] = msg;
  doc["timestamp"] = millis();
  serializeJson(doc, Serial);
  Serial.println();
}
