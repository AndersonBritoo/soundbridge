# =============================================================
#  SoundBridge – Gateway Configuration
#  Path: gateway/config.py
#  All tuneable parameters in one place.
#  Edit this file to adapt the gateway to your environment
# =============================================================

# ── Serial ────────────────────────────────────────────────────
SERIAL_PORT     = "COM3"          # Windows: "COM3" | Linux/Mac: "/dev/ttyUSB0"
BAUDRATE        = 115_200
SERIAL_TIMEOUT  = 1               # seconds – readline timeout

# ── API ───────────────────────────────────────────────────────
API_URL         = "http://localhost:8000/morse"
API_TIMEOUT     = 5               # seconds per request
API_RETRIES     = 3               # attempts before giving up
API_RETRY_DELAY = 2               # seconds between retries

# ── Identity ─────────────────────────────────────────────────
DEVICE_ID       = "esp32_01"

# ── Logging ───────────────────────────────────────────────────
LOG_LEVEL       = "DEBUG"         # DEBUG | INFO | WARNING | ERROR
LOG_FORMAT      = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%H:%M:%S"