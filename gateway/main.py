#!/usr/bin/env python3
# =============================================================
#  SoundBridge – Gateway Entry Point
#  Path: gateway/main.py
#  Bridges ESP32 serial events directly to the API.
#  All Morse processing now happens on the API side.
#
#  Usage
#  -----
#  python gateway/main.py
#
#  Stop with Ctrl-C.
# =============================================================

import logging
import sys
import time

# Adjust path so the package resolves correctly when run directly
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gateway.config        import LOG_LEVEL, LOG_FORMAT, LOG_DATE_FORMAT
from gateway.serial_reader import SerialReader
from gateway.api_client    import ApiClient


def _configure_logging() -> None:
    """Initialise root logger from config values."""
    level = getattr(logging, LOG_LEVEL.upper(), logging.DEBUG)
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
        stream=sys.stdout,
    )


def run() -> None:
    """
    Main loop – reads ESP32 messages and forwards them to the API.

    The Gateway no longer processes Morse logic.
    It acts as a simple bridge: Serial → API.

    The loop is designed to be indestructible:
    - Serial errors are handled inside SerialReader (auto-reconnect).
    - API errors are handled inside ApiClient (retry + log).
    - Any unexpected exception here is caught, logged, and the loop
      resumes after a 1-second pause.
    """
    _configure_logging()
    logger = logging.getLogger(__name__)

    logger.info("=" * 56)
    logger.info("  SoundBridge Gateway  –  starting (bridge mode)")
    logger.info("=" * 56)

    with SerialReader() as reader, ApiClient() as api:
        logger.info("Listening on '%s'…  (Ctrl-C to stop)", reader.port)

        while True:
            try:
                message = reader.read_message()

                if message is None:
                    # No data this tick – yield CPU briefly
                    time.sleep(0.01)
                    continue

                logger.debug("MSG ← %s", message)

                # Extract event details from ESP32 message
                event_type = message.get("type")
                value = message.get("value")
                timestamp = message.get("timestamp")

                # Handle system messages locally (no need to forward)
                if event_type == "system":
                    logger.info("ESP32: %s", message.get("message"))
                    continue

                # Forward all other events directly to API
                if event_type:
                    api.send_event(event_type=event_type, value=value, timestamp=timestamp)
                else:
                    logger.warning("Message missing 'type' field – ignored: %s", message)

            except KeyboardInterrupt:
                logger.info("Interrupted by user – shutting down.")
                break

            except Exception as exc:             # noqa: BLE001
                # Log but never let the loop die
                logger.exception("Unhandled exception: %s – resuming in 1 s…", exc)
                time.sleep(1)

    logger.info("Gateway stopped.")


if __name__ == "__main__":
    run()