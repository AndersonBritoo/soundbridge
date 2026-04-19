# =============================================================
#  SoundBridge – Morse Service
#  Path: api/services/morse_service.py
#  Morse code decoding functionality
# =============================================================
"""
Serviço de descodificação de código Morse.

Este módulo encapsula a tabela de tradução Morse e a lógica de descodificação
de sequências individuais (ponto/traço → carácter). É utilizado pelo
``DeviceService`` para converter cada letra Morse no seu carácter correspondente
durante o processamento de eventos ``letter_end``.

A tabela ``_MORSE_TABLE`` segue o código Morse internacional (ITU), cobrindo
letras maiúsculas (A–Z), dígitos (0–9) e os sinais de pontuação mais comuns.

Depende de: módulo padrão ``logging``.
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


# ── Morse Code Translation Table ─────────────────────────────
# Dicionário de tradução Morse → carácter, com 54 entradas.
# A estrutura é invertida relativamente à notação humana habitual
# (carácter → Morse): aqui a chave é a sequência de pontos e traços,
# e o valor é o carácter correspondente, o que permite lookup O(1) direto
# durante a descodificação sem necessidade de iterar a tabela.
# Cobertura: 26 letras (A–Z), 10 dígitos (0–9) e 18 sinais de pontuação.
_MORSE_TABLE: Dict[str, str] = {
    # Letras — código Morse internacional (ITU) para o alfabeto latino
    ".-": "A", "-...": "B", "-.-.": "C", "-..": "D",
    ".": "E", "..-.": "F", "--.": "G", "....": "H",
    "..": "I", ".---": "J", "-.-": "K", ".-..": "L",
    "--": "M", "-.": "N", "---": "O", ".--.": "P",
    "--.-": "Q", ".-.": "R", "...": "S", "-": "T",
    "..-": "U", "...-": "V", ".--": "W", "-..-": "X",
    "-.--": "Y", "--..": "Z",
    # Dígitos — representações numéricas 0–9 em Morse ITU
    "-----": "0", ".----": "1", "..---": "2", "...--": "3",
    "....-": "4", ".....": "5", "-....": "6", "--...": "7",
    "---..": "8", "----.": "9",
    # Pontuação — sinais tipográficos comuns em Morse ITU
    ".-.-.-": ".", "--..--": ",", "..--..": "?",
    ".----.": "'", "-.-.--": "!", "-..-.": "/",
    "-.--.": "(", "-.--.-": ")", ".-...": "&",
    "---...": ":", "-.-.-.": ";", "-...-": "=",
    ".-.-.": "+", "-....-": "-", ".-..-.": '"',
    ".--.-.": "@",
}


class MorseService:
    """Serviço stateless de operações sobre o código Morse.

    Não mantém estado de instância — todos os métodos são estáticos e operam
    sobre a tabela ``_MORSE_TABLE`` definida ao nível do módulo. Pode ser
    instanciado normalmente (como em ``DeviceService.__init__``) ou chamado
    diretamente via ``MorseService.morse_to_char()``.
    """

    @staticmethod
    def morse_to_char(code: str) -> str | None:
        """Descodifica uma sequência Morse num único carácter.

        Realiza normalização defensiva via ``strip()`` antes do lookup, o que
        garante que espaços acidentais no início ou fim da sequência (que podem
        ocorrer em payloads mal formatados do firmware) não causam falhas de
        descodificação desnecessárias.

        Opta por registar um warning em vez de lançar exceção para sequências
        desconhecidas: esta abordagem é mais resiliente em contexto de hardware
        (o firmware pode gerar sequências inválidas por ruído ou timing incorreto)
        e permite que a palavra em curso continue a ser processada, descartando
        apenas a letra inválida.

        Args:
            code (str): Sequência de pontos e traços a descodificar
                (ex: ``".-"`` ou ``"..."``)。

        Returns:
            str | None: O carácter correspondente (ex: ``"A"``), ou ``None`` se
                a sequência não existir na tabela Morse. O ``dict.get()`` devolve
                ``None`` por defeito quando a chave não existe, sem lançar exceção.
        """
        # strip() como normalização defensiva: remove espaços acidentais que
        # poderiam fazer falhar o lookup mesmo para sequências Morse válidas.
        stripped = code.strip()
        if not stripped:
            return None

        # dict.get() devolve None (sem exceção) para sequências não reconhecidas,
        # permitindo ao chamador decidir como tratar a ausência de resultado.
        char = _MORSE_TABLE.get(stripped)
        if char is None:
            # Regista warning em vez de lançar exceção: sequências desconhecidas
            # são descartadas silenciosamente, mantendo a resiliência do sistema
            # face a ruído de hardware ou firmware experimental.
            logger.warning("Unknown Morse sequence: '%s' – skipping.", stripped)
        else:
            logger.debug("Decoded '%s' → '%s'.", stripped, char)

        return char

    @staticmethod
    def get_morse_table() -> Dict[str, str]:
        """Devolve uma cópia da tabela de tradução Morse completa.

        Devolve uma cópia via ``dict.copy()`` em vez da referência direta à
        tabela original ``_MORSE_TABLE``, protegendo-a de modificações externas
        acidentais. Destinada a uso em testes, documentação ou endpoints de
        introspecção que necessitem de expor a tabela de tradução.

        Returns:
            Dict[str, str]: Dicionário com todas as sequências Morse como chaves
                e os caracteres correspondentes como valores. As modificações ao
                dicionário devolvido não afetam a tabela interna do módulo.
        """
        return _MORSE_TABLE.copy()