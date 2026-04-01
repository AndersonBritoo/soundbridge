# 🌉 SoundBridge

Sistema IoT para captura, interpretação e armazenamento de sinais em Código Morse.

---

## 📖 Descrição

O **SoundBridge** é um sistema distribuído que permite captar sinais físicos através de um botão ligado a um ESP32, convertê-los em Código Morse (`.` e `-`), processar esses sinais em tempo real e armazenar o resultado numa base de dados.

O sistema está dividido em três camadas principais:

* **ESP32 (Hardware)** → captação de sinais
* **Gateway (Python)** → comunicação e envio de dados
* **API (FastAPI)** → processamento, lógica e armazenamento

---

## 🧠 Objetivo

Demonstrar uma arquitetura completa de integração entre:

* Sistemas embebidos (ESP32)
* Comunicação Serial (USB)
* Processamento em tempo real
* APIs REST (FastAPI)
* Bases de dados relacionais (MySQL)

---

## ⚙️ Arquitetura do Sistema

```
    [Utilizador]
         ↓
      [ESP32]
         ↓            (Serial - JSON)
  [Gateway (Python)]
         ↓            (HTTP - JSON)
   [API (FastAPI)]
         ↓
[Base de Dados (MySQL)]
```

---

## 🔌 Hardware Utilizado

* ESP32
* Botão (GPIO 5)
* LED Azul (GPIO 12) → Ponto `.`
* LED Vermelho (GPIO 13) → Traço `-`

---

## 🔁 Funcionamento do Sistema

1. O utilizador pressiona o botão no ESP32
2. O ESP32 mede a duração do clique:

   * Curto → `.`
   * Longo → `-`
3. O ESP32 envia eventos em JSON via Serial
4. O Gateway:

   * Lê os dados
   * Envia diretamente para a API
5. A API:

   * Processa os sinais Morse
   * Reconstrói letras e palavras
   * Armazena na base de dados

---

## 🧾 Protocolo de Comunicação

### Sinais

```json
{ "type": "signal", "value": ".", "timestamp": 123456 }
{ "type": "signal", "value": "-", "timestamp": 123456 }
```

### Eventos

```json
{ "type": "letter_end", "timestamp": 123456 }
{ "type": "word_end", "timestamp": 123456 }
```

---

## 🧩 Estrutura do Projeto

```
soundbridge/
│
├── esp32/
│   └── soundbridge/
│       └── soundbridge.ino       # Firmware do ESP32
│
├── gateway/
│   ├── main.py                  # Loop principal
│   ├── serial_reader.py         # Leitura da Serial
│   ├── api_client.py            # Comunicação com API
│   └── config.py                # Configurações
│
├── api/
│   ├── main.py                  # Inicialização da API
│   │
│   ├── routes/
│   │   └── morse.py             # Endpoints
│   │
│   ├── services/
│   │   ├── device_service.py    # Estado dos dispositivos
│   │   └── morse_service.py     # Lógica Morse
│   │
│   ├── db/
│   │   ├── connection.py        # Ligação à base de dados
│   │   └── repository.py        # Queries
│   │
│   ├── models/
│   │   └── morse.py             # Modelos Pydantic
│   │
│   └── core/
│       └── config.py            # Configurações e logging
│
├── database/
│   └── structure.sql            # Estrutura da base de dados
│
├── logs/
│   ├── api/
│   └── gateway/
│
├── .gitignore
├── LICENSE
└── README.md
```

---

## 🗄️ Base de Dados

Tabela principal: `mensagens`

| Campo     | Tipo     | Descrição           |
| --------- | -------- | ------------------- |
| id        | INT      | Identificador único |
| device_id | VARCHAR  | ID do dispositivo   |
| morse     | TEXT     | Código Morse        |
| text      | TEXT     | Texto interpretado  |
| timestamp | DATETIME | Data/hora do evento |

---

## 🚀 Como Executar o Projeto

### 1. Instalar dependências

```bash
pip install -r requirements.txt
```

---

### 2. Configurar Base de Dados

* Iniciar MySQL (ex: XAMPP)
* Executar o ficheiro:

```sql
database/structure.sql
```

---

### 3. Iniciar API

```bash
uvicorn api.main:app --reload
```

Aceder a:
👉 [http://localhost:8000/docs](http://localhost:8000/docs)

---

### 4. Configurar Gateway

Editar:

```python
SERIAL_PORT = "COM3"
```

---

### 5. Iniciar Gateway

```bash
python gateway/main.py
```

---

### 6. Executar ESP32

* Upload do código para o ESP32
* Ligar via USB

---

## 📊 Funcionalidades

* Captura de input físico (botão)
* Classificação de sinais (ponto/traço)
* Separação automática de letras e palavras
* Processamento de Morse na API
* Comunicação Serial com JSON
* Comunicação com API REST
* Armazenamento em base de dados
* Estrutura modular e escalável

---

## 📌 Estado do Projeto

🚧 Em desenvolvimento
📍 Sistema base funcional (ESP32 + Gateway + API + DB)

---

## 🔮 Próximos Passos

* Comunicação via WiFi (ESP32 → API)
* Suporte a múltiplos dispositivos
* Dashboard / interface web
* Deploy em servidor (VM / Proxmox)
* Interface gráfica no ESP32 (display)

---

## 📌 GitHub

[https://github.com/AndersonBritoo/soundbridge](https://github.com/AndersonBritoo/soundbridge)

---

## 👨‍💻 Autor

Andérson
Curso GPSI - 12º Ano