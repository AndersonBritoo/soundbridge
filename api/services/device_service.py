# =============================================================
#  SoundBridge – Device Service
#  Path: api/services/device_service.py
#  Device state management and Morse event processing
# =============================================================
"""
Máquina de estados por dispositivo para processamento de eventos Morse em tempo real.

Este módulo implementa a lógica de acumulação e descodificação de sinais Morse
recebidos do ESP32 evento a evento. Cada dispositivo tem o seu próprio estado
independente, gerido pelo ``DeviceService`` através de um dicionário indexado
por ``device_id``.

O fluxo normal de eventos para uma palavra é:
    ``signal`` (+) → ... → ``letter_end`` → ``signal`` (+) → ... → ``letter_end``
    → ``word_end``

O módulo é resiliente a firmware que omita ``letter_end`` antes de ``word_end``:
nesse caso, a letra pendente é descarregada automaticamente no ``word_end``.

Depende de: ``api.services.morse_service.MorseService``.
"""

import logging
from typing import Dict, List, Tuple

from api.services.morse_service import MorseService

logger = logging.getLogger(__name__)


class DeviceState:
    """Estado da máquina de estados Morse para um único dispositivo.

    Mantém três buffers independentes que representam o progresso de descodificação
    em curso para um dispositivo específico:

    - ``current_letter``: acumula os pontos e traços do sinal Morse da letra
      atualmente em construção. É reiniciado após cada ``letter_end``.
    - ``current_word_morse``: lista de sequências Morse das letras já descodificadas
      na palavra em curso (ex: ``["...", "---", "..."]``). É reiniciado após
      cada ``word_end``.
    - ``current_word_text``: lista de caracteres já descodificados na palavra em
      curso (ex: ``["S", "O", "S"]``). É reiniciado após cada ``word_end``.

    A separação entre ``current_letter`` e os buffers de palavra é intencional:
    ``current_letter`` representa trabalho em curso (letra ainda não terminada),
    enquanto os buffers de palavra representam letras já confirmadas e descodificadas.

    Attributes:
        device_id (str): Identificador do dispositivo a que este estado pertence.
        current_letter (str): Buffer de pontos e traços da letra em construção.
        current_word_morse (List[str]): Sequências Morse das letras confirmadas
            na palavra em curso.
        current_word_text (List[str]): Caracteres descodificados das letras
            confirmadas na palavra em curso.
    """

    def __init__(self, device_id: str):
        self.device_id = device_id
        self.current_letter = ""  # accumulator for current letter
        self.current_word_morse: List[str] = []  # Morse codes for current word
        self.current_word_text: List[str] = []  # decoded chars for current word

    def reset(self) -> None:
        """Limpa completamente o estado do dispositivo.

        Chamado explicitamente pelo endpoint de reset (via ``DeviceService.reset_device``)
        ou em situações de recuperação de erro. Reinicia os três buffers para os
        seus valores iniciais, descartando qualquer letra ou palavra em curso.
        Após este método, o dispositivo está pronto para receber uma nova sequência
        de eventos como se acabasse de ser registado pela primeira vez.
        """
        self.current_letter = ""
        self.current_word_morse = []
        self.current_word_text = []
        logger.debug("[%s] State reset.", self.device_id)


class DeviceService:
    """Serviço de gestão de estados e processamento de eventos Morse por dispositivo.

    Mantém um dicionário ``_device_states`` que mapeia cada ``device_id`` ao seu
    objeto ``DeviceState`` correspondente. Os estados são criados lazily no primeiro
    evento recebido de cada dispositivo, não sendo necessária pré-configuração.

    Depende do ``MorseService`` para a descodificação de sequências Morse em
    caracteres, mantendo a separação de responsabilidades: este serviço gere o
    estado e o fluxo de eventos; o ``MorseService`` gere o conhecimento da tabela
    de códigos Morse.

    Attributes:
        _device_states (Dict[str, DeviceState]): Dicionário de estados ativos,
            indexado por ``device_id``.
        _morse_service (MorseService): Instância do serviço de descodificação Morse.
    """

    def __init__(self):
        self._device_states: Dict[str, DeviceState] = {}
        self._morse_service = MorseService()

    def get_device_state(self, device_id: str) -> DeviceState:
        """Obtém ou cria o estado da máquina de estados para um dispositivo.

        Implementa criação lazy: se o ``device_id`` ainda não tiver estado
        registado, um novo ``DeviceState`` é criado e armazenado no dicionário.
        Isto permite que novos dispositivos se registem automaticamente no
        primeiro evento enviado, sem configuração prévia.

        Args:
            device_id (str): Identificador único do dispositivo ESP32.

        Returns:
            DeviceState: O objeto de estado existente ou recém-criado para
                este dispositivo.
        """
        if device_id not in self._device_states:
            self._device_states[device_id] = DeviceState(device_id)
            logger.info("[%s] New device state created.", device_id)
        return self._device_states[device_id]

    def process_signal(self, state: DeviceState, value: str) -> None:
        """Processa um evento de sinal: acumula ponto ou traço no buffer da letra.

        Args:
            state (DeviceState): Estado do dispositivo a atualizar.
            value (str): Valor do sinal Morse recebido. Deve ser ``"."`` (ponto)
                ou ``"-"`` (traço).
        """
        # Valida o valor antes de acumular — rejeita silenciosamente valores
        # inesperados (ex: string vazia, espaço) que corrompiam o buffer da letra
        # e produziriam sequências Morse inválidas na descodificação.
        if value not in (".", "-"):
            logger.warning(
                "[%s] Unexpected signal value '%s' – ignoring.",
                state.device_id, value
            )
            return

        # Acumula o sinal no buffer da letra em curso; a concatenação constrói
        # progressivamente a sequência Morse (ex: "." → ".." → "..." para "S").
        state.current_letter += value
        logger.debug(
            "[%s] signal '%s' │ letter_morse='%s'",
            state.device_id, value, state.current_letter
        )

    def process_letter_end(self, state: DeviceState) -> None:
        """Processa um evento de fim de letra: descodifica o buffer e actualiza os buffers de palavra.

        Args:
            state (DeviceState): Estado do dispositivo a atualizar.
        """
        code = state.current_letter
        # Guarda contra buffer vazio: pode ocorrer se o firmware enviar
        # "letter_end" sem sinais precedentes (ex: duplo "letter_end" por
        # debounce no hardware). Neste caso ignora silenciosamente o evento.
        if not code:
            logger.debug("[%s] letter_end with empty buffer – skipped.", state.device_id)
            return

        # Lookup na tabela Morse via MorseService — devolve None se a sequência
        # não for reconhecida, permitindo descartar a letra sem crashar.
        char = self._morse_service.morse_to_char(code)
        if char:
            # Adiciona a sequência Morse e o carácter descodificado em paralelo
            # aos respectivos buffers de palavra, mantendo a correspondência
            # índice-a-índice entre morse e texto (necessária para construir
            # as strings finais com join em process_word_end).
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

        # Reinicia o buffer da letra após a descodificação (com ou sem sucesso),
        # preparando o estado para receber os sinais da letra seguinte.
        state.current_letter = ""

    def process_word_end(self, state: DeviceState) -> Tuple[str, str] | None:
        """Processa um evento de fim de palavra: finaliza e devolve a palavra completa.

        Antes de construir a palavra final, verifica se existe uma letra pendente
        no buffer ``current_letter`` (o que ocorre quando o firmware não envia
        ``letter_end`` antes de ``word_end``). Se existir, força o flush dessa
        letra chamando ``process_letter_end`` — comportamento de resiliência a
        firmware que omite o evento intermédio.

        Args:
            state (DeviceState): Estado do dispositivo a finalizar.

        Returns:
            Tuple[str, str] | None: Par ``(morse_str, text_str)`` com a palavra
                completa pronta para persistência, ou ``None`` se o buffer de
                palavra estiver vazio (word_end sem conteúdo válido).
        """
        # Flush automático de letra pendente: se o firmware enviou "word_end"
        # sem "letter_end" precedente, a última letra ficaria perdida sem este passo.
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

        # Constrói as strings finais a partir dos buffers:
        # - morse_str: letras separadas por espaço (formato canónico Morse entre letras)
        # - text_str: caracteres concatenados sem separador (palavra em texto simples)
        morse_str = " ".join(state.current_word_morse)
        text_str = "".join(state.current_word_text)

        logger.info(
            "[%s] word_end │ text='%s'  morse='%s'",
            state.device_id, text_str, morse_str
        )

        # Reinicia apenas os buffers de palavra — não o current_letter, porque
        # já foi limpo pelo process_letter_end chamado no flush acima.
        # O estado fica pronto para receber a próxima palavra.
        state.current_word_morse = []
        state.current_word_text = []

        return morse_str, text_str

    def reset_device(self, device_id: str) -> None:
        """Reinicia o estado de um dispositivo específico.

        Se o dispositivo não tiver estado registado, o método termina
        silenciosamente sem erro.

        Args:
            device_id (str): Identificador do dispositivo a reiniciar.
        """
        if device_id in self._device_states:
            self._device_states[device_id].reset()

    def get_all_device_ids(self) -> List[str]:
        """Devolve a lista de identificadores de todos os dispositivos com estado activo.

        Returns:
            List[str]: Lista de ``device_id`` de todos os dispositivos atualmente
                rastreados pelo serviço.
        """
        return list(self._device_states.keys())