##
# @file        config.py
# @path        gateway/config.py
# @brief       Fonte única de verdade para todas as constantes configuráveis do gateway SoundBridge.
#
# @details     Este ficheiro centraliza todos os parâmetros ajustáveis do sistema: porta série, URL da API,
#              temporização, número de tentativas, identidade do dispositivo e nível de registo (logging).
#              Nenhuma lógica de negócio reside aqui; o ficheiro é importado pelos restantes módulos do gateway.
#              Não efectua qualquer I/O nem inicializa recursos – limita-se a definir constantes em tempo de importação.
#              Ocupa o topo da hierarquia de dependências: nenhum outro módulo do projecto é importado a partir daqui.
#
# @dependencies  (nenhuma dependência interna do projecto)
#
# @limitations   Todos os valores são constantes em tempo de execução; alterações requerem reinício do gateway.
#                Não existe validação dos valores definidos – um valor inválido (ex.: baudrate errado ou URL
#                malformada) só será detectado quando o módulo que o utiliza tentar usá-lo.
##

# ── Série (Serial) ────────────────────────────────────────────
# COUPLING: SERIAL_PORT, BAUDRATE e SERIAL_TIMEOUT são lidos directamente por SerialReader.__init__(); alterar
#           estes valores afecta imediatamente o comportamento da ligação ao ESP32.

SERIAL_PORT     = "COM3"          # Windows: "COM3" | Linux/Mac: "/dev/ttyUSB0"
BAUDRATE        = 115_200
SERIAL_TIMEOUT  = 1               # segundos – tempo máximo de espera em readline

# ── API ───────────────────────────────────────────────────────
# COUPLING: API_URL, API_TIMEOUT, API_RETRIES e API_RETRY_DELAY são lidos por ApiClient.__init__(); qualquer alteração
#           aqui repercute-se em todas as instâncias de ApiClient.

API_URL         = "http://localhost:8000/morse"
API_TIMEOUT     = 5               # segundos por pedido HTTP
API_RETRIES     = 3               # tentativas antes de desistir
API_RETRY_DELAY = 2               # segundos de espera entre tentativas

# ── Identidade ────────────────────────────────────────────────
# Identificador único do dispositivo enviado em cada evento para a API, permitindo distinguir múltiplos gateways na mesma instalação.

DEVICE_ID       = "esp32_01"

# ── Registo (Logging) ─────────────────────────────────────────
# COUPLING: LOG_LEVEL, LOG_FORMAT e LOG_DATE_FORMAT são importados directamente em main.py por _configure_logging();
#           alterar estes valores modifica o comportamento do registo em todo o gateway.

LOG_LEVEL       = "DEBUG"         # DEBUG | INFO | WARNING | ERROR
LOG_FORMAT      = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%H:%M:%S"