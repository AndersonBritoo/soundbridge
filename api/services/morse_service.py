# =============================================================
#  SoundBridge – Morse Service
#  Path: api/services/morse_service.py
#  Morse code decoding functionality
# =============================================================

import logging
from typing import Dict

logger = logging.getLogger(__name__)


# ── Morse Code Translation Table ─────────────────────────────
_MORSE_TABLE: Dict[str, str] = {
    # Letters
    ".-": "A", "-...": "B", "-.-.": "C", "-..": "D",
    ".": "E", "..-.": "F", "--.": "G", "....": "H",
    "..": "I", ".---": "J", "-.-": "K", ".-..": "L",
    "--": "M", "-.": "N", "---": "O", ".--.": "P",
    "--.-": "Q", ".-.": "R", "...": "S", "-": "T",
    "..-": "U", "...-": "V", ".--": "W", "-..-": "X",
    "-.--": "Y", "--..": "Z",
    # Digits
    "-----": "0", ".----": "1", "..---": "2", "...--": "3",
    "....-": "4", ".....": "5", "-....": "6", "--...": "7",
    "---..": "8", "----.": "9",
    # Punctuation
    ".-.-.-": ".", "--..--": ",", "..--..": "?",
    ".----.": "'", "-.-.--": "!", "-..-.": "/",
    "-.--.": "(", "-.--.-": ")", ".-...": "&",
    "---...": ":", "-.-.-.": ";", "-...-": "=",
    ".-.-.": "+", "-....-": "-", ".-..-.": '"',
    ".--.-.": "@",
}


class MorseService:
    """Service for Morse code decoding operations."""
    
    @staticmethod
    def morse_to_char(code: str) -> str | None:
        """
        Decode a single Morse sequence into its character.
        
        Parameters
        ----------
        code : str
            A string of dots and dashes, e.g. ".-" or "..."
            
        Returns
        -------
        str | None
            The decoded character, or None if the code is unknown
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
    
    @staticmethod
    def get_morse_table() -> Dict[str, str]:
        """
        Get the complete Morse code translation table.
        
        Returns
        -------
        Dict[str, str]
            Dictionary mapping Morse sequences to characters
        """
        return _MORSE_TABLE.copy()