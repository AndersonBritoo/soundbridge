# =============================================================
#  SoundBridge – Morse Decoder
#  Path: gateway/morse_decoder.py
#  Converts individual Morse sequences (e.g. ".-") into their
#  corresponding characters.
#
#  Public API
#  ----------
#  morse_to_char(code: str) -> str | None
#      Decode a single Morse sequence.
#  morse_to_text(codes: list[str]) -> str
#      Decode a list of sequences into a word string.
# =============================================================

import logging

logger = logging.getLogger(__name__)

# ── Morse → Character lookup table ───────────────────────────
# Covers A–Z, 0–9, and the most common punctuation marks.
_MORSE_TABLE: dict[str, str] = {
    # ── Letters ──────────────────────────────────────────────
    ".-":    "A",  
    "-...":  "B",  
    "-.-.":  "C",  
    "-..":   "D",
    ".":     "E",  
    "..-.":  "F",  
    "--.":   "G",  
    "....":  "H",
    "..":    "I",  
    ".---":  "J",  
    "-.-":   "K",  
    ".-..":  "L",
    "--":    "M",  
    "-.":    "N",  
    "---":   "O",  
    ".--.":  "P",
    "--.-":  "Q",  
    ".-.":   "R",  
    "...":   "S",  
    "-":     "T",
    "..-":   "U",  
    "...-":  "V",  
    ".--":   "W",  
    "-..-":  "X",
    "-.--":  "Y",  
    "--..":  "Z",

    # ── Digits ───────────────────────────────────────────────
    "-----": "0",  
    ".----": "1",  
    "..---": "2",  
    "...--": "3",
    "....-": "4",  
    ".....": "5",  
    "-....": "6",  
    "--...": "7",
    "---..": "8",  
    "----.": "9",

    # ── Punctuation ──────────────────────────────────────────
    ".-.-.-": ".",   
    "--..--": ",",   
    "..--..": "?",
    ".----.": "'",   
    "-.-.--": "!",   
    "-..-.":  "/",
    "-.--.":  "(",   
    "-.--.-": ")",   
    ".-...":  "&",
    "---...": ":",   
    "-.-.-.": ";",   
    "-...-":  "=",
    ".-.-.":  "+",   
    "-....-": "-",   
    ".-..-.": '"',
    ".--.-.": "@",
}


def morse_to_char(code: str) -> str | None:
    """
    Translate a single Morse sequence into its character.

    Parameters
    ----------
    code : str
        A string of dots and dashes, e.g. ``".-"`` or ``"..."``.

    Returns
    -------
    str | None
        The decoded character, or ``None`` if the code is unknown.
    """
    stripped = code.strip()
    if not stripped:
        return None

    char = _MORSE_TABLE.get(stripped)
    if char is None:
        logger.warning("Unknown Morse sequence: '%s' – skipping.", stripped)
    else:
        logger.debug("Decoded '%s' → '%s'.", stripped, char)

    return char


def morse_to_text(codes: list[str]) -> str:
    """
    Decode a list of Morse sequences into a word string.

    Unrecognised codes are silently dropped.

    Parameters
    ----------
    codes : list[str]
        Ordered list of per-letter Morse sequences.

    Returns
    -------
    str
        Concatenated decoded characters (empty string if nothing decoded).
    """
    chars = (morse_to_char(c) for c in codes)
    return "".join(ch for ch in chars if ch is not None)