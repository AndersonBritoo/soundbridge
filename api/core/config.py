# =============================================================
#  SoundBridge – Configuration
#  Path: api/core/config.py
#  Centralized configuration and logging setup
# =============================================================

import logging
import os
from typing import Dict


# ── Logging Configuration ────────────────────────────────────
def setup_logging() -> None:
    """Configure application-wide logging."""
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


# ── Database Configuration ────────────────────────────────────
class DatabaseConfig:
    """Database connection configuration."""
    
    HOST: str = os.getenv("DB_HOST", "localhost")
    PORT: int = int(os.getenv("DB_PORT", "3306"))
    USER: str = os.getenv("DB_USER", "root")
    PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DATABASE: str = os.getenv("DB_NAME", "soundbridge")
    POOL_SIZE: int = 5
    
    @classmethod
    def get_config(cls) -> Dict[str, any]:
        """Return database configuration as a dictionary."""
        return {
            "host": cls.HOST,
            "port": cls.PORT,
            "user": cls.USER,
            "password": cls.PASSWORD,
            "database": cls.DATABASE,
        }


# ── Application Metadata ──────────────────────────────────────
class AppConfig:
    """Application metadata configuration."""
    
    TITLE: str = "SoundBridge"
    DESCRIPTION: str = "Receives raw ESP32 events, processes Morse, and stores completed words."
    VERSION: str = "2.2.1"