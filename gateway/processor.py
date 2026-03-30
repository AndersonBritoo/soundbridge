# =============================================================
#  SoundBridge – Event Processor
#  Path: gateway/processor.py
#  Stateful machine that turns raw ESP32 events into words.
#
#  State
#  -----
#  _letter_morse  : str        dots/dashes for the letter being typed
#  _word_morse    : list[str]  per-letter Morse codes of the current word
#  _word_chars    : list[str]  decoded characters of the current word
#
#  Event flow
#  ----------
#  signal "." / "-"  →  append to _letter_morse
#  letter_end        →  decode _letter_morse, append char to _word_chars
#  word_end          →  flush pending letter, emit word, reset state
# =============================================================

import logging

from gateway.morse_decoder import morse_to_char
from gateway.api_client    import ApiClient

logger = logging.getLogger(__name__)


class MorseProcessor:
    """
    Receives parsed ESP32 messages and drives the decode → send pipeline.
    """

    # Event type constants matching the ESP32 protocol
    _EV_SIGNAL     = "signal"
    _EV_LETTER_END = "letter_end"
    _EV_WORD_END   = "word_end"
    _EV_SYSTEM     = "system"

    def __init__(self, api_client: ApiClient) -> None:
        self._api          = api_client
        self._letter_morse = ""           # accumulator for current letter
        self._word_morse:  list[str] = [] # Morse codes for current word
        self._word_chars:  list[str] = [] # decoded chars for current word

    # ── Public interface ──────────────────────────────────────

    def handle(self, message: dict) -> None:
        """
        Dispatch a parsed JSON message from the ESP32.

        Parameters
        ----------
        message : dict
            Decoded JSON object, e.g. ``{"type": "signal", "value": "."}``.
        """
        ev = message.get("type")

        if   ev == self._EV_SIGNAL:     self._on_signal(message.get("value", ""))
        elif ev == self._EV_LETTER_END: self._on_letter_end()
        elif ev == self._EV_WORD_END:   self._on_word_end()
        elif ev == self._EV_SYSTEM:     logger.info("ESP32: %s", message.get("message"))
        else:                           logger.debug("Unknown event '%s' – ignored.", ev)

    def reset(self) -> None:
        """Clear all accumulated state (useful for tests / re-initialisation)."""
        self._letter_morse = ""
        self._word_morse   = []
        self._word_chars   = []
        logger.debug("Processor state cleared.")

    # ── Private handlers ──────────────────────────────────────

    def _on_signal(self, value: str) -> None:
        """Append a dot or dash to the active letter buffer."""
        if value not in (".", "-"):
            logger.warning("Unexpected signal value '%s' – ignoring.", value)
            return

        self._letter_morse += value
        logger.debug("signal '%s' │ letter_morse='%s'", value, self._letter_morse)

    def _on_letter_end(self) -> None:
        """
        Decode the accumulated Morse sequence for one letter,
        add the result to the word buffer, and reset the letter accumulator.
        """
        code = self._letter_morse
        if not code:
            logger.debug("letter_end with empty buffer – skipped.")
            return

        char = morse_to_char(code)
        if char:
            self._word_morse.append(code)
            self._word_chars.append(char)
            logger.info(
                "letter_end │ '%s' ← '%s'  │  word so far: '%s'",
                char, code, "".join(self._word_chars),
            )
        else:
            logger.warning("letter_end │ unrecognised Morse '%s' – dropped.", code)

        self._letter_morse = ""

    def _on_word_end(self) -> None:
        """
        Finalise and dispatch the current word.

        1. Flush any pending letter (guards against missed letter_end events).
        2. Assemble the full word string.
        3. Send it to the API.
        4. Reset word-level state.
        """
        # Flush dangling letter if letter_end was not received
        if self._letter_morse:
            logger.debug("word_end: flushing pending letter '%s'.", self._letter_morse)
            self._on_letter_end()

        if not self._word_chars:
            logger.debug("word_end with empty word buffer – nothing to send.")
            return

        morse_str = " ".join(self._word_morse)
        text_str  = "".join(self._word_chars)

        logger.info("word_end │ text='%s'  morse='%s'", text_str, morse_str)

        self._api.send_word(morse=morse_str, text=text_str)

        # Reset for the next word
        self._word_morse = []
        self._word_chars = []