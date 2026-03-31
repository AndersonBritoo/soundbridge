#!/usr/bin/env python3
# =============================================================
#  SoundBridge – FastAPI Backend
#  Path: api/main.py
#  Receives raw ESP32 events, processes Morse logic, and
#  persists completed words to MySQL.
#
#  Run
#  ---
#  uvicorn api.main:app --reload --port 8000
#  – or –
#  python api/main.py
#
#  Endpoints
#  ---------
#  POST /morse          Accept event or legacy word payload
#  GET  /morse          List all stored messages
#  GET  /morse/{id}     Retrieve a single message
#  GET  /health         Liveness probe
#
#  Stop with Ctrl-C.
# =============================================================

import logging
import os
from contextlib import asynccontextmanager
from datetime   import datetime
from typing     import Dict, List, Any

import mysql.connector
import mysql.connector.pooling
from fastapi            import FastAPI, HTTPException, status
from fastapi.responses  import JSONResponse
from pydantic           import BaseModel, Field

# ── Logging ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Database configuration ────────────────────────────────────
DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "port":     int(os.getenv("DB_PORT", "3306")),
    "user":     os.getenv("DB_USER",     "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": "soundbridge",
}
POOL_SIZE = 5   # concurrent connections available to the API

# Module-level pool reference (initialised inside lifespan)
_pool: mysql.connector.pooling.MySQLConnectionPool | None = None

# ── Morse Decoder (copied from gateway/morse_decoder.py) ─────
_MORSE_TABLE: Dict[str, str] = {
    # Letters
    ".-":    "A",  "-...":  "B",  "-.-.":  "C",  "-..":   "D",
    ".":     "E",  "..-.":  "F",  "--.":   "G",  "....":  "H",
    "..":    "I",  ".---":  "J",  "-.-":   "K",  ".-..":  "L",
    "--":    "M",  "-.":    "N",  "---":   "O",  ".--.":  "P",
    "--.-":  "Q",  ".-.":   "R",  "...":   "S",  "-":     "T",
    "..-":   "U",  "...-":  "V",  ".--":   "W",  "-..-":  "X",
    "-.--":  "Y",  "--..":  "Z",
    # Digits
    "-----": "0",  ".----": "1",  "..---": "2",  "...--": "3",
    "....-": "4",  ".....": "5",  "-....": "6",  "--...": "7",
    "---..": "8",  "----.": "9",
    # Punctuation
    ".-.-.-": ".",   "--..--": ",",   "..--..": "?",
    ".----.": "'",   "-.-.--": "!",   "-..-.":  "/",
    "-.--.":  "(",   "-.--.-": ")",   ".-...":  "&",
    "---...": ":",   "-.-.-.": ";",   "-...-":  "=",
    ".-.-.":  "+",   "-....-": "-",   ".-..-.": '"',
    ".--.-.": "@",
}


def morse_to_char(code: str) -> str | None:
    """Decode a single Morse sequence into its character."""
    stripped = code.strip()
    if not stripped:
        return None
    
    char = _MORSE_TABLE.get(stripped)
    if char is None:
        logger.warning("Unknown Morse sequence: '%s' – skipping.", stripped)
    else:
        logger.debug("Decoded '%s' → '%s'.", stripped, char)
    
    return char


# ── Device State Management ───────────────────────────────────

class DeviceState:
    """Stateful Morse processor for a single device."""
    
    def __init__(self, device_id: str):
        self.device_id = device_id
        self.current_letter = ""           # accumulator for current letter
        self.current_word_morse: List[str] = []  # Morse codes for current word
        self.current_word_text: List[str] = []   # decoded chars for current word
    
    def reset(self):
        """Clear all state."""
        self.current_letter = ""
        self.current_word_morse = []
        self.current_word_text = []
        logger.debug("[%s] State reset.", self.device_id)


# Global state storage: device_id → DeviceState
device_states: Dict[str, DeviceState] = {}


def get_device_state(device_id: str) -> DeviceState:
    """Get or create a DeviceState for the given device."""
    if device_id not in device_states:
        device_states[device_id] = DeviceState(device_id)
        logger.info("[%s] New device state created.", device_id)
    return device_states[device_id]


# =============================================================
#  Lifespan – create / destroy connection pool
# =============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create the MySQL connection pool at startup; close it on shutdown."""
    global _pool
    try:
        _pool = mysql.connector.pooling.MySQLConnectionPool(
            pool_name="soundbridge_pool",
            pool_size=POOL_SIZE,
            **DB_CONFIG,
        )
        logger.info("MySQL connection pool created (size=%d).", POOL_SIZE)
    except mysql.connector.Error as exc:
        logger.error("Cannot create MySQL pool: %s", exc)
        # App will start but every DB call will fail gracefully

    yield  # ← application runs here

    _pool = None
    logger.info("MySQL pool released.")


# =============================================================
#  FastAPI application
# =============================================================

app = FastAPI(
    title="SoundBridge API",
    description="Receives raw ESP32 events, processes Morse, and stores completed words.",
    version="2.0.0",
    lifespan=lifespan,
)


# ── Helper: get a pooled connection ──────────────────────────

def _get_connection() -> mysql.connector.pooling.PooledMySQLConnection:
    """
    Return a connection from the pool.
    Raises HTTP 503 if the pool is unavailable.
    """
    if _pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database pool not initialised.",
        )
    try:
        return _pool.get_connection()
    except mysql.connector.Error as exc:
        logger.error("Pool connection error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable.",
        ) from exc


# ── Helper: insert word into database ────────────────────────

def _insert_word(device_id: str, morse: str, text: str, timestamp: datetime | None = None) -> int:
    """
    Insert a completed Morse word into the database.
    Returns the new row ID.
    """
    if timestamp is None:
        timestamp = datetime.now()
    
    conn   = _get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO mensagens (device_id, morse, text, timestamp)
            VALUES (%s, %s, %s, %s)
            """,
            (device_id, morse, text, timestamp),
        )
        conn.commit()
        new_id = cursor.lastrowid
        logger.info("[%s] Inserted mensagens.id=%d  text='%s'", device_id, new_id, text)
        return new_id
    except mysql.connector.Error as exc:
        conn.rollback()
        logger.error("[%s] DB insert failed: %s", device_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database insert failed.",
        ) from exc
    finally:
        cursor.close()
        conn.close()


# =============================================================
#  Pydantic models
# =============================================================

class MorseEvent(BaseModel):
    """Raw event from ESP32 (NEW format)."""
    device_id: str
    type: str  # "signal", "letter_end", "word_end"
    value: str | None = None  # "." or "-" for signal events
    timestamp: int | None = None


class MorseMessage(BaseModel):
    """Legacy payload format (OLD format – for backwards compatibility)."""
    device_id: str  = Field(...,  example="esp32_01")
    morse:     str  = Field(...,  example="... --- ...")
    text:      str  = Field(...,  example="SOS")
    timestamp: str  = Field(...,  example="2024-05-01T12:00:00+00:00",
                                  description="ISO 8601 datetime string")


class MorseRecord(BaseModel):
    """Row returned from the database."""
    id:        int
    device_id: str
    morse:     str
    text:      str
    timestamp: datetime


# =============================================================
#  Event Processing Logic
# =============================================================

def process_signal(state: DeviceState, value: str) -> None:
    """Handle a signal event: append dot or dash to current letter."""
    if value not in (".", "-"):
        logger.warning("[%s] Unexpected signal value '%s' – ignoring.", state.device_id, value)
        return
    
    state.current_letter += value
    logger.debug("[%s] signal '%s' │ letter_morse='%s'", state.device_id, value, state.current_letter)


def process_letter_end(state: DeviceState) -> None:
    """Handle letter_end: decode current letter and add to word buffers."""
    code = state.current_letter
    if not code:
        logger.debug("[%s] letter_end with empty buffer – skipped.", state.device_id)
        return
    
    char = morse_to_char(code)
    if char:
        state.current_word_morse.append(code)
        state.current_word_text.append(char)
        logger.info(
            "[%s] letter_end │ '%s' ← '%s'  │  word so far: '%s'",
            state.device_id, char, code, "".join(state.current_word_text),
        )
    else:
        logger.warning("[%s] letter_end │ unrecognised Morse '%s' – dropped.", state.device_id, code)
    
    state.current_letter = ""


def process_word_end(state: DeviceState) -> None:
    """Handle word_end: finalize and save the word to database."""
    # Flush dangling letter if letter_end was not received
    if state.current_letter:
        logger.debug("[%s] word_end: flushing pending letter '%s'.", state.device_id, state.current_letter)
        process_letter_end(state)
    
    if not state.current_word_text:
        logger.debug("[%s] word_end with empty word buffer – nothing to send.", state.device_id)
        return
    
    morse_str = " ".join(state.current_word_morse)
    text_str  = "".join(state.current_word_text)
    
    logger.info("[%s] word_end │ text='%s'  morse='%s'", state.device_id, text_str, morse_str)
    
    # Insert into database
    _insert_word(state.device_id, morse_str, text_str)
    
    # Reset word-level state
    state.current_word_morse = []
    state.current_word_text = []


# =============================================================
#  Endpoints
# =============================================================

@app.post(
    "/morse",
    status_code=status.HTTP_201_CREATED,
    summary="Receive event or legacy word payload",
)
def receive_morse(payload: Dict[str, Any]):
    """
    Accept either:
    1. NEW format: raw ESP32 event (type: signal/letter_end/word_end)
    2. OLD format: completed Morse word (morse, text, timestamp fields)
    
    The format is auto-detected based on the presence of the 'type' field.
    """
    # Detect format
    if "type" in payload:
        # NEW FORMAT: raw event from ESP32
        try:
            event = MorseEvent(**payload)
        except Exception as exc:
            logger.error("Invalid event payload: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid event format: {exc}",
            ) from exc
        
        logger.debug("[%s] Received event: type='%s'  value='%s'", 
                    event.device_id, event.type, event.value)
        
        # Get device state
        state = get_device_state(event.device_id)
        
        # Process event
        if event.type == "signal":
            if event.value:
                process_signal(state, event.value)
        elif event.type == "letter_end":
            process_letter_end(state)
        elif event.type == "word_end":
            process_word_end(state)
        else:
            logger.warning("[%s] Unknown event type '%s' – ignored.", event.device_id, event.type)
        
        return {"status": "processed"}
    
    else:
        # OLD FORMAT: legacy complete word payload
        try:
            msg = MorseMessage(**payload)
        except Exception as exc:
            logger.error("Invalid legacy payload: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid payload format: {exc}",
            ) from exc
        
        # Parse the ISO timestamp string into a Python datetime
        try:
            dt = datetime.fromisoformat(msg.timestamp)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid timestamp format: {exc}",
            ) from exc
        
        logger.info(
            "[%s] POST /morse (legacy) │ text='%s'  morse='%s'",
            msg.device_id, msg.text, msg.morse,
        )
        
        # Insert directly (bypass state machine)
        new_id = _insert_word(msg.device_id, msg.morse, msg.text, dt)
        
        return {"id": new_id, "status": "stored"}


@app.get(
    "/morse",
    response_model=list[MorseRecord],
    summary="List all stored messages",
)
def list_morse(limit: int = 100, offset: int = 0):
    """Return up to *limit* rows, ordered by most recent first."""
    conn   = _get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT * FROM mensagens ORDER BY timestamp DESC LIMIT %s OFFSET %s",
            (limit, offset),
        )
        rows = cursor.fetchall()
    except mysql.connector.Error as exc:
        logger.error("DB select failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database query failed.",
        ) from exc
    finally:
        cursor.close()
        conn.close()

    return rows


@app.get(
    "/morse/{message_id}",
    response_model=MorseRecord,
    summary="Retrieve a single message by ID",
)
def get_morse(message_id: int):
    """Return one row by primary key, or 404 if not found."""
    conn   = _get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM mensagens WHERE id = %s", (message_id,))
        row = cursor.fetchone()
    except mysql.connector.Error as exc:
        logger.error("DB select by id failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database query failed.",
        ) from exc
    finally:
        cursor.close()
        conn.close()

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")

    return row


@app.get("/health", summary="Liveness probe")
def health():
    """Quick check that the API process is alive."""
    return {"status": "ok"}


# =============================================================
#  Development runner
# =============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)