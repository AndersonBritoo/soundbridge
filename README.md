# 🌉 SoundBridge

Sistema IoT para captura, interpretação e armazenamento de sinais em Código Morse.

## 📖 Descrição

O **SoundBridge** é um projeto que utiliza um microcontrolador (ESP32) para captar interações físicas (botão), converter em sinais Morse (`.` e `-`), enviar esses dados para um gateway, que por sua vez interpreta e envia para uma API, sendo finalmente armazenados numa base de dados.

---

## 🧠 Objetivo

Demonstrar a integração completa entre:

- Hardware (ESP32)
- Comunicação Serial
- Processamento em Python (Gateway)
- API REST (FastAPI)
- Base de Dados (MySQL)
- Captura de input físico (botão)
- Conversão em sinais Morse
- Separação automática de letras e palavras
- Comunicação Serial com JSON
- Interpretação em tempo real
- Envio para API REST
- Armazenamento em base de dados

---

## ⚙️ Arquitetura do Sistema

```

[Utilizador]
↓
[ESP32]
↓ (Serial - JSON)
[Gateway (Python)]
↓ (HTTP - JSON)
[API (FastAPI)]
↓
[Base de Dados (MySQL)]

````

---

## 🔌 Hardware Utilizado

- ESP32
- Botão (GPIO 5)
- LED Azul (GPIO 12) → Ponto `.`
- LED Vermelho (GPIO 13) → Traço `-`

---

## 🧾 Protocolo de Comunicação

O ESP32 envia dados em formato JSON via Serial:

### Sinais
```json
{ "type": "signal", "value": ".", "timestamp": 123456 }
{ "type": "signal", "value": "-", "timestamp": 123456 }
````

### Eventos

```json
{ "type": "letter_end", "timestamp": 123456 }
{ "type": "word_end", "timestamp": 123456 }
```

### Sistema

```json
{ "type": "system", "message": "ready", "timestamp": 123456 }
```

---

## 🧩 Estrutura do Projeto

```
soundbridge/
│
├── esp32/
│
├── gateway/
│
├── api/
│
└── db/
```

---

## 📊 Funcionalidades

* Captura de input físico (botão)
* Conversão em sinais Morse
* Separação automática de letras e palavras
* Comunicação Serial com JSON
* Interpretação em tempo real
* Envio para API REST
* Armazenamento em base de dados

---

## 📌 Estado do Projeto

🚧 Em desenvolvimento (Projeto Final de Curso)

---

## 📌 GitHub

https://github.com/AndersonBritoo/soundbridge/tree/master

---

## 👨‍💻 Autor

Andérson
Curso GPSI - 12º Ano