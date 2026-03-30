# =============================================================
#  SoundBridge – Serial Reader
#  Path: gateway/serial_reader.py
#  Manages the USB serial connection to the ESP32.
#
#  Responsibilities
#  ----------------
#  • Open / close the serial port
#  • Auto-reconnect on cable disconnection or port errors
#  • Read one line at a time and return a parsed JSON dict
#  • Silently discard lines that are not valid JSON
# =============================================================

import json
import logging
import time

import serial
import serial.serialutil

from gateway import config

logger = logging.getLogger(__name__)


class SerialReader:
    """
    Wraps a pyserial connection and exposes ``read_message()``.

    Usage (context manager – recommended)
    --------------------------------------
    >>> with SerialReader() as reader:
    ...     while True:
    ...         msg = reader.read_message()
    ...         if msg:
    ...             process(msg)
    """

    def __init__(
        self,
        port: str      = config.SERIAL_PORT,
        baudrate: int  = config.BAUDRATE,
        timeout: float = config.SERIAL_TIMEOUT,
    ) -> None:
        self.port     = port
        self.baudrate = baudrate
        self.timeout  = timeout
        self._serial: serial.Serial | None = None

    # ── Connection management ─────────────────────────────────

    def connect(self) -> None:
        """
        Open the serial port, blocking until it succeeds.
        Retries every 3 s so the gateway survives hot-plug events.
        """
        while True:
            try:
                self._serial = serial.Serial(
                    port=self.port,
                    baudrate=self.baudrate,
                    timeout=self.timeout,
                )
                logger.info("Serial '%s' opened at %d baud.", self.port, self.baudrate)
                return
            except serial.serialutil.SerialException as exc:
                logger.error("Cannot open '%s': %s – retrying in 3 s…", self.port, exc)
                time.sleep(3)

    def disconnect(self) -> None:
        """Close the port gracefully (no-op if already closed)."""
        if self._serial and self._serial.is_open:
            self._serial.close()
            logger.info("Serial '%s' closed.", self.port)

    # ── Reading ───────────────────────────────────────────────

    def read_message(self) -> dict | None:
        """
        Read one line from the serial port and parse it as JSON.

        Returns
        -------
        dict | None
            Parsed message, or ``None`` when:
            - the line timed out (no data)
            - the line was not valid JSON
            - a port error occurred (triggers reconnect automatically)
        """
        # Guard: reconnect if port somehow closed
        if self._serial is None or not self._serial.is_open:
            logger.warning("Serial not open – reconnecting…")
            self.connect()
            return None

        try:
            raw: bytes = self._serial.readline()   # b"" on timeout
        except serial.serialutil.SerialException as exc:
            logger.error("Serial read error: %s – reconnecting…", exc)
            self.disconnect()
            self.connect()
            return None

        if not raw:
            return None  # normal timeout, no data available

        line = raw.decode("utf-8", errors="ignore").strip()
        if not line:
            return None

        logger.debug("RAW ← '%s'", line)

        try:
            return json.loads(line)
        except json.JSONDecodeError:
            logger.debug("Not valid JSON – discarding: '%s'", line)
            return None

    # ── Context manager ───────────────────────────────────────

    def __enter__(self) -> "SerialReader":
        self.connect()
        return self

    def __exit__(self, *_) -> None:
        self.disconnect()