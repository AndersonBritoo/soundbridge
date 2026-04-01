# =============================================================
#  SoundBridge – Data Models
#  Path: api/models/morse.py
#  Pydantic models for request/response validation
# =============================================================

from datetime import datetime
from pydantic import BaseModel, Field


class MorseEvent(BaseModel):
    """Raw event from ESP32 (NEW format)."""
    device_id: str
    type: str  # "signal", "letter_end", "word_end"
    value: str | None = None  # "." or "-" for signal events
    timestamp: int | None = None


class MorseMessage(BaseModel):
    """Legacy payload format (OLD format – for backwards compatibility)."""
    device_id: str = Field(..., example="esp32_01")
    morse: str = Field(..., example="... --- ...")
    text: str = Field(..., example="SOS")
    timestamp: str = Field(
        ...,
        example="2024-05-01T12:00:00+00:00",
        description="ISO 8601 datetime string"
    )


class MorseRecord(BaseModel):
    """Row returned from the database."""
    id: int
    device_id: str
    morse: str
    text: str
    timestamp: datetime