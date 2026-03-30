#!/usr/bin/env python3
# =============================================================
#  SoundBridge – Gateway Entry Point
#  Path: gateway/main.py
#  Wires SerialReader → MorseProcessor → ApiClient together
#  and runs the main event loop.
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
from gateway.processor     import MorseProcessor
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
    Main loop – reads ESP32 messages and feeds them to the processor.

    The loop is designed to be indestructible:
    - Serial errors are handled inside SerialReader (auto-reconnect).
    - API errors are handled inside ApiClient (retry + log).
    - Any unexpected exception here is caught, logged, and the loop
      resumes after a 1-second pause.
    """
    _configure_logging()
    logger = logging.getLogger(__name__)

    logger.info("=" * 56)
    logger.info("  SoundBridge Gateway  –  starting")
    logger.info("=" * 56)

    with SerialReader() as reader, ApiClient() as api:
        processor = MorseProcessor(api_client=api)
        logger.info("Listening on '%s'…  (Ctrl-C to stop)", reader.port)

        while True:
            try:
                message = reader.read_message()

                if message is None:
                    # No data this tick – yield CPU briefly
                    time.sleep(0.01)
                    continue

                logger.debug("MSG ← %s", message)
                processor.handle(message)

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