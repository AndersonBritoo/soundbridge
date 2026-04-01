# =============================================================
#  SoundBridge – Device Service
#  Path: api/services/device_service.py
#  Device state management and Morse event processing
# =============================================================

import logging
from typing import Dict, List, Tuple

from api.services.morse_service import MorseService

logger = logging.getLogger(__name__)


class DeviceState:
    """Stateful Morse processor for a single device."""
    
    def __init__(self, device_id: str):
        self.device_id = device_id
        self.current_letter = ""  # accumulator for current letter
        self.current_word_morse: List[str] = []  # Morse codes for current word
        self.current_word_text: List[str] = []  # decoded chars for current word
    
    def reset(self) -> None:
        """Clear all state."""
        self.current_letter = ""
        self.current_word_morse = []
        self.current_word_text = []
        logger.debug("[%s] State reset.", self.device_id)


class DeviceService:
    """Service for managing device states and processing Morse events."""
    
    def __init__(self):
        self._device_states: Dict[str, DeviceState] = {}
        self._morse_service = MorseService()
    
    def get_device_state(self, device_id: str) -> DeviceState:
        """
        Get or create a DeviceState for the given device.
        
        Parameters
        ----------
        device_id : str
            Unique identifier for the device
            
        Returns
        -------
        DeviceState
            The state object for this device
        """
        if device_id not in self._device_states:
            self._device_states[device_id] = DeviceState(device_id)
            logger.info("[%s] New device state created.", device_id)
        return self._device_states[device_id]
    
    def process_signal(self, state: DeviceState, value: str) -> None:
        """
        Handle a signal event: append dot or dash to current letter.
        
        Parameters
        ----------
        state : DeviceState
            The device state to update
        value : str
            Signal value ("." or "-")
        """
        if value not in (".", "-"):
            logger.warning(
                "[%s] Unexpected signal value '%s' – ignoring.",
                state.device_id, value
            )
            return
        
        state.current_letter += value
        logger.debug(
            "[%s] signal '%s' │ letter_morse='%s'",
            state.device_id, value, state.current_letter
        )
    
    def process_letter_end(self, state: DeviceState) -> None:
        """
        Handle letter_end: decode current letter and add to word buffers.
        
        Parameters
        ----------
        state : DeviceState
            The device state to update
        """
        code = state.current_letter
        if not code:
            logger.debug("[%s] letter_end with empty buffer – skipped.", state.device_id)
            return
        
        char = self._morse_service.morse_to_char(code)
        if char:
            state.current_word_morse.append(code)
            state.current_word_text.append(char)
            logger.info(
                "[%s] letter_end │ '%s' ← '%s'  │  word so far: '%s'",
                state.device_id, char, code, "".join(state.current_word_text),
            )
        else:
            logger.warning(
                "[%s] letter_end │ unrecognised Morse '%s' – dropped.",
                state.device_id, code
            )
        
        state.current_letter = ""
    
    def process_word_end(self, state: DeviceState) -> Tuple[str, str] | None:
        """
        Handle word_end: finalize the word and return it for storage.
        
        Parameters
        ----------
        state : DeviceState
            The device state to finalize
            
        Returns
        -------
        Tuple[str, str] | None
            Tuple of (morse_str, text_str) if word is complete, None otherwise
        """
        # Flush dangling letter if letter_end was not received
        if state.current_letter:
            logger.debug(
                "[%s] word_end: flushing pending letter '%s'.",
                state.device_id, state.current_letter
            )
            self.process_letter_end(state)
        
        if not state.current_word_text:
            logger.debug(
                "[%s] word_end with empty word buffer – nothing to send.",
                state.device_id
            )
            return None
        
        morse_str = " ".join(state.current_word_morse)
        text_str = "".join(state.current_word_text)
        
        logger.info(
            "[%s] word_end │ text='%s'  morse='%s'",
            state.device_id, text_str, morse_str
        )
        
        # Reset word-level state
        state.current_word_morse = []
        state.current_word_text = []
        
        return morse_str, text_str
    
    def reset_device(self, device_id: str) -> None:
        """
        Reset the state for a specific device.
        
        Parameters
        ----------
        device_id : str
            Device identifier to reset
        """
        if device_id in self._device_states:
            self._device_states[device_id].reset()
    
    def get_all_device_ids(self) -> List[str]:
        """
        Get list of all device IDs currently being tracked.
        
        Returns
        -------
        List[str]
            List of device identifiers
        """
        return list(self._device_states.keys())