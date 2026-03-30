# =============================================================
#  SoundBridge – API Client
#  Path: gateway/api_client.py
#  Sends completed Morse words to the FastAPI backend.
#
#  Features
#  --------
#  • Persistent HTTP session (connection reuse)
#  • Configurable retry with delay between attempts
#  • Full error handling – never raises, always logs
# =============================================================

import logging
import time
from datetime import datetime, timezone

import requests

from gateway import config

logger = logging.getLogger(__name__)


class ApiClient:
    """
    Thin wrapper around ``requests.Session`` that posts word
    payloads to the configured endpoint.
    """

    def __init__(
        self,
        url: str            = config.API_URL,
        timeout: int        = config.API_TIMEOUT,
        retries: int        = config.API_RETRIES,
        retry_delay: float  = config.API_RETRY_DELAY,
        device_id: str      = config.DEVICE_ID,
    ) -> None:
        self.url         = url
        self.timeout     = timeout
        self.retries     = retries
        self.retry_delay = retry_delay
        self.device_id   = device_id

        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    # ── Public interface ──────────────────────────────────────

    def send_word(self, morse: str, text: str) -> bool:
        """
        POST a completed Morse word to the API.

        Parameters
        ----------
        morse : str
            Space-separated per-letter Morse sequences, e.g. ``"... --- ..."``.
        text  : str
            Decoded plain-text word, e.g. ``"SOS"``.

        Returns
        -------
        bool
            ``True`` on success (2xx response), ``False`` if all
            retry attempts failed.
        """
        payload = {
            "device_id": self.device_id,
            "morse":     morse,
            "text":      text,
            # ISO 8601 timestamp with UTC timezone
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        logger.info("→ API | morse='%s'  text='%s'", morse, text)

        for attempt in range(1, self.retries + 1):
            try:
                resp = self._session.post(self.url, json=payload, timeout=self.timeout)
                resp.raise_for_status()
                logger.info("API accepted (HTTP %d) on attempt %d.", resp.status_code, attempt)
                return True

            except requests.exceptions.ConnectionError as exc:
                logger.warning("Attempt %d/%d – connection error: %s", attempt, self.retries, exc)

            except requests.exceptions.Timeout:
                logger.warning(
                    "Attempt %d/%d – timed out after %ds.", attempt, self.retries, self.timeout
                )

            except requests.exceptions.HTTPError as exc:
                logger.error("Attempt %d/%d – HTTP error: %s", attempt, self.retries, exc)

            except requests.exceptions.RequestException as exc:
                logger.error("Attempt %d/%d – request failed: %s", attempt, self.retries, exc)

            # Wait before next attempt (skip delay on the last attempt)
            if attempt < self.retries:
                logger.info("Retrying in %gs…", self.retry_delay)
                time.sleep(self.retry_delay)

        logger.error("All %d attempt(s) failed for word '%s' – data lost.", self.retries, text)
        return False

    def close(self) -> None:
        """Release the underlying HTTP session."""
        self._session.close()

    # ── Context manager ───────────────────────────────────────

    def __enter__(self) -> "ApiClient":
        return self

    def __exit__(self, *_) -> None:
        self.close()