#!/usr/bin/env python3
# =============================================================
#  SoundBridge – FastAPI Backend
#  Receives decoded Morse words from the Gateway and persists
#  them to MySQL.
#
#  Run
#  ---
#  uvicorn api.main:app --reload --port 8000
#  – or –
#  python api/main.py
#
#  Endpoints
#  ---------
#  POST /morse          Accept a word from the gateway
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
    description="Receives Morse code words from the ESP32 gateway and stores them.",
    version="1.0.0",
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


# =============================================================
#  Pydantic models
# =============================================================

class MorseMessage(BaseModel):
    """Payload sent by the gateway on every word_end event."""
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
#  Endpoints
# =============================================================

@app.post(
    "/morse",
    status_code=status.HTTP_201_CREATED,
    summary="Store a decoded Morse word",
)
def receive_morse(payload: MorseMessage):
    """
    Accept a decoded Morse word from the gateway and insert it
    into the ``mensagens`` table.
    """
    # Parse the ISO timestamp string into a Python datetime
    try:
        dt = datetime.fromisoformat(payload.timestamp)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid timestamp format: {exc}",
        ) from exc

    logger.info(
        "POST /morse │ device='%s'  text='%s'  morse='%s'",
        payload.device_id, payload.text, payload.morse,
    )

    conn   = _get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO mensagens (device_id, morse, text, timestamp)
            VALUES (%s, %s, %s, %s)
            """,
            (payload.device_id, payload.morse, payload.text, dt),
        )
        conn.commit()
        new_id = cursor.lastrowid
        logger.info("Inserted mensagens.id=%d.", new_id)
    except mysql.connector.Error as exc:
        conn.rollback()
        logger.error("DB insert failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database insert failed.",
        ) from exc
    finally:
        cursor.close()
        conn.close()   # returns connection to pool

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