# =============================================================
#  SoundBridge – Morse Routes
#  Path: api/routes/morse.py
#  API endpoints for Morse message handling
# =============================================================

import logging
from datetime import datetime
from typing import Dict, Any, List

from fastapi import APIRouter, HTTPException, status

from api.models.morse import MorseEvent, MorseMessage, MorseRecord
from api.services.device_service import DeviceService
from api.db.repository import MorseRepository

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Initialize services (singleton pattern)
device_service = DeviceService()
repository = MorseRepository()


@router.post(
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
        
        logger.debug(
            "[%s] Received event: type='%s'  value='%s'",
            event.device_id, event.type, event.value
        )
        
        # Get device state
        state = device_service.get_device_state(event.device_id)
        
        # Process event
        if event.type == "signal":
            if event.value:
                device_service.process_signal(state, event.value)
        elif event.type == "letter_end":
            device_service.process_letter_end(state)
        elif event.type == "word_end":
            result = device_service.process_word_end(state)
            if result:
                morse_str, text_str = result
                # Insert into database
                repository.insert_word(event.device_id, morse_str, text_str)
        else:
            logger.warning(
                "[%s] Unknown event type '%s' – ignored.",
                event.device_id, event.type
            )
        
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
        new_id = repository.insert_word(msg.device_id, msg.morse, msg.text, dt)
        
        return {"id": new_id, "status": "stored"}


@router.get(
    "/morse",
    response_model=List[MorseRecord],
    summary="List all stored messages",
)
def list_morse(limit: int = 100, offset: int = 0):
    """Return up to *limit* rows, ordered by most recent first."""
    rows = repository.get_all_messages(limit=limit, offset=offset)
    return rows

@router.get(
    "/morse/latest",
    summary="Return the most recently inserted message",
)
def get_latest_morse():
    """
    Return the latest record in mensagens.
    
    Returns a lightweight JSON suitable for ESP32 polling:
    - 200 + record  → message found
    - 200 + status  → table is empty (no 404, easier to parse on ESP32)
    """
    row = repository.get_latest_message()

    if row is None:
        logger.info("GET /morse/latest → empty table.")
        return {"status": "empty"}

    logger.info(
        "GET /morse/latest → id=%d  device='%s'  text='%s'",
        row["id"], row["device_id"], row["text"],
    )
    return row


@router.get(
    "/morse/{message_id}",
    response_model=MorseRecord,
    summary="Retrieve a single message by ID",
)
def get_morse(message_id: int):
    """Return one row by primary key, or 404 if not found."""
    row = repository.get_message_by_id(message_id)
    
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found."
        )
    
    return row


@router.get("/health", summary="Liveness probe")
def health():
    """Quick check that the API process is alive."""
    return {"status": "ok"}