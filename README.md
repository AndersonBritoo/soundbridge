# SoundBridge

SoundBridge é um sistema embebido de comunicação por código Morse, composto por firmware para ESP32, um gateway serial-HTTP e uma API REST com base de dados MySQL. O utilizador pressiona um botão físico para introduzir sinais Morse; o sistema descodifica-os em tempo real e persiste as palavras resultantes, que ficam disponíveis para consulta via display TFT ou API.

---

## Arquitetura do Sistema

```
┌─────────────────────────────────────────────────────────┐
│                      ESP32 Firmware                     │
│  Botão → Morse → JSON Serial  |  TFT Display ← Poll HTTP│
└────────────────┬────────────────────────────────────────┘
                 │ USB Serial (JSON)
┌────────────────▼────────────────────────────────────────┐
│                        Gateway                          │
│         SerialReader → ApiClient → HTTP POST            │
└────────────────┬────────────────────────────────────────┘
                 │ HTTP REST
┌────────────────▼────────────────────────────────────────┐
│                       API (FastAPI)                     │
│  routes → services → repository → MySQL                 │
└─────────────────────────────────────────────────────────┘
```

### Componentes

| Componente | Tecnologia | Localização |
|---|---|---|
| Firmware | C++ / PlatformIO / ESP32 | `firmware/esp32/` |
| Gateway | Python / pyserial / requests | `gateway/` |
| API | Python / FastAPI / MySQL | `api/` |
| Base de Dados | MySQL / MariaDB | `db/` |

---

## Estrutura do Projeto

```
soundbridge/
├── api/                    # API REST (FastAPI)
│   ├── main.py             # Ponto de entrada; instância FastAPI e lifespan
│   ├── core/
│   │   └── config.py       # Configuração centralizada (DB, logging, metadados)
│   ├── db/
│   │   ├── connection.py   # Pool de conexões MySQL
│   │   └── repository.py   # Operações CRUD (repository pattern)
│   ├── models/
│   │   └── morse.py        # Modelos Pydantic (MorseEvent, MorseMessage, MorseRecord)
│   ├── routes/
│   │   └── morse.py        # Endpoints HTTP
│   ├── services/
│   │   ├── device_service.py  # Máquina de estados por dispositivo
│   │   └── morse_service.py   # Tabela de descodificação Morse
│   └── requirements.txt
├── db/
│   └── schema.sql          # Schema MySQL
├── firmware/
│   └── esp32/
│       ├── src/            # Código-fonte C++
│       │   ├── main.cpp
│       │   ├── button.cpp
│       │   ├── leds.cpp
│       │   ├── morse.cpp
│       │   ├── poller.cpp
│       │   ├── soundbridge_wifi.cpp
│       │   └── ui.cpp
│       ├── include/        # Headers
│       │   └── config.h    # Todas as constantes do firmware
│       └── platformio.ini
└── gateway/                # Ponte Serial → API
    ├── main.py
    ├── serial_reader.py
    ├── api_client.py
    └── config.py
```

---

## Pré-requisitos

### API
- Python 3.10+
- MySQL 8.0+ ou MariaDB 10.6+

### Gateway
- Python 3.10+
- ESP32 ligado via USB

### Firmware
- [PlatformIO](https://platformio.org/) (CLI ou extensão VS Code)
- Placa ESP32 com display TFT ST7789 e botão físico

---

## Instalação e Execução

### 1. Base de Dados

```bash
mysql -u root -p < db/schema.sql
```

Cria a base de dados `soundbridge` e a tabela `mensagens`.

### 2. API

```bash
cd api
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Criar ficheiro `.env` na raiz de `api/`:

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=soundbridge
DB_PASSWORD=<password>
DB_NAME=soundbridge
```

Iniciar o servidor:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

A documentação interativa fica disponível em `http://localhost:8000/docs`.

### 3. Gateway

```bash
cd gateway
pip install pyserial requests
```

Editar `gateway/config.py` com a porta serial correta (ex: `COM3` no Windows, `/dev/ttyUSB0` no Linux) e o endereço da API.

```bash
python main.py
```

### 4. Firmware

Editar `firmware/esp32/include/config.h` com as credenciais Wi-Fi e o endereço do servidor da API.

```bash
cd firmware/esp32
pio run --target upload
```

---

## Endpoints da API

| Método | Path | Descrição |
|---|---|---|
| `POST` | `/morse` | Recebe evento do ESP32 (sinal, letter_end, word_end) ou payload legado |
| `GET` | `/morse` | Lista mensagens com paginação (`limit`, `offset`) |
| `GET` | `/morse/latest` | Última mensagem inserida |
| `GET` | `/morse/{id}` | Mensagem por ID |
| `GET` | `/health` | Estado da API |

### Exemplos de payload (POST `/morse`)

**Formato novo (firmware atual):**
```json
{ "device_id": "esp32_01", "type": "signal", "value": "." }
{ "device_id": "esp32_01", "type": "letter_end" }
{ "device_id": "esp32_01", "type": "word_end" }
```

**Formato legado:**
```json
{
  "device_id": "esp32_01",
  "morse": "... --- ...",
  "text": "SOS",
  "timestamp": "2024-05-01T12:00:00+00:00"
}
```

---

## Schema da Base de Dados

```sql
CREATE TABLE mensagens (
    id         INT          AUTO_INCREMENT PRIMARY KEY,
    device_id  VARCHAR(50)  NOT NULL,
    morse      TEXT         NOT NULL,
    text       TEXT         NOT NULL,
    timestamp  DATETIME     NOT NULL,
    INDEX idx_device   (device_id),
    INDEX idx_timestamp(timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## Fluxo de Dados

```
[Botão pressionado]
       ↓
button.cpp → duração da pressão
       ↓
morse.cpp → classifica "." ou "-" → JSON para Serial
       ↓
gateway/serial_reader.py → lê linha JSON
       ↓
gateway/api_client.py → POST /morse
       ↓
api/routes/morse.py → deteta tipo de evento
       ↓
api/services/device_service.py → máquina de estados
       ↓  (em word_end)
api/services/morse_service.py → descodifica Morse → texto
       ↓
api/db/repository.py → INSERT INTO mensagens
       ↓
[firmware/poller.cpp] → GET /morse/latest a cada 5s
       ↓
ui.cpp → atualiza display TFT
```

---

## Licença

Consultar [LICENSE](LICENSE).

## Autor

Andérson