# =============================================================
#  SoundBridge – Data Models
#  Path: api/models/morse.py
#  Pydantic models for request/response validation
# =============================================================
"""
Modelos Pydantic de validação e serialização para a API SoundBridge.

Este módulo define três modelos distintos, cada um correspondendo a um
formato diferente de dados no ciclo de vida de uma mensagem Morse:

- ``MorseEvent``: representa um evento individual enviado pelo ESP32 em tempo
  real (formato novo), que pode ser um sinal, o fim de uma letra ou o fim de
  uma palavra.
- ``MorseMessage``: representa o payload completo no formato legado, onde o
  ESP32 envia a palavra já descodificada com morse, texto e timestamp.
- ``MorseRecord``: representa uma linha completa lida da base de dados,
  incluindo o ID gerado e o timestamp como objeto ``datetime``.

A separação em três modelos evita ambiguidades na validação e torna explícitas
as fronteiras entre entrada (ESP32 → API) e saída (API → cliente/ESP32).
"""

from datetime import datetime
from pydantic import BaseModel, Field


class MorseEvent(BaseModel):
    """Evento individual enviado pelo ESP32 no formato novo.

    Instanciada pelo router ``POST /morse`` quando o payload contém o campo
    ``type``, indicando que provém do firmware atualizado do ESP32. Representa
    a unidade mínima de informação: um único sinal (ponto ou traço), o sinal
    de fim de letra ou o sinal de fim de palavra.

    Attributes:
        device_id (str): Identificador único do dispositivo que enviou o evento.
        type (str): Discriminador do tipo de evento. Valores possíveis:
            ``"signal"`` (sinal Morse), ``"letter_end"`` (fim de letra) ou
            ``"word_end"`` (fim de palavra). Define qual método do
            ``DeviceService`` será invocado.
        value (str | None): Valor do sinal Morse: ``"."`` (ponto) ou ``"-"``
            (traço). Apenas presente em eventos do tipo ``"signal"``; nos
            restantes tipos é ``None`` pois não há valor associado.
        timestamp (int | None): Instante do evento como inteiro (millisegundos
            Unix epoch), conforme enviado pelo firmware do ESP32. Pode ser
            ``None`` se o dispositivo não tiver relógio sincronizado.
    """

    device_id: str
    # O campo type serve como discriminador de formato: a sua presença no payload
    # JSON é o critério usado pelo router para distinguir eventos novos de payloads
    # legados (que não incluem este campo).
    type: str  # "signal", "letter_end", "word_end"
    # O valor é opcional porque só faz sentido em eventos "signal";
    # eventos "letter_end" e "word_end" não transportam valor associado.
    value: str | None = None  # "." or "-" for signal events
    # O timestamp é int em MorseEvent (millisegundos Unix epoch, conforme o
    # firmware ESP32) por oposição a str em MorseMessage (ISO 8601) e a
    # datetime em MorseRecord (objeto Python após leitura da base de dados).
    timestamp: int | None = None


class MorseMessage(BaseModel):
    """Payload completo no formato legado (compatibilidade retroativa).

    Instanciada pelo router ``POST /morse`` quando o payload não contém o campo
    ``type``, indicando que provém de firmware antigo que já envia a palavra
    completa e descodificada. Neste caso a máquina de estados é contornada e
    o registo é persistido diretamente.

    Attributes:
        device_id (str): Identificador do dispositivo de origem.
        morse (str): Sequência Morse da palavra com letras separadas por espaço.
        text (str): Texto descodificado correspondente à sequência Morse.
        timestamp (str): Instante da mensagem em formato ISO 8601 (ex:
            ``"2024-05-01T12:00:00+00:00"``). É uma string neste modelo porque
            é enviada diretamente pelo firmware; será convertida para ``datetime``
            pelo router antes de persistir na base de dados.
    """

    device_id: str = Field(..., example="esp32_01")
    morse: str = Field(..., example="... --- ...")
    text: str = Field(..., example="SOS")
    # O timestamp é str aqui porque o firmware legado envia um string ISO 8601.
    # O router é responsável por converter este valor para datetime via
    # datetime.fromisoformat() antes de chamar o repositório.
    timestamp: str = Field(
        ...,
        example="2024-05-01T12:00:00+00:00",
        description="ISO 8601 datetime string"
    )


class MorseRecord(BaseModel):
    """Registo completo lido da base de dados.

    Instanciada pelo FastAPI para serializar as respostas dos endpoints de
    consulta (``GET /morse``, ``GET /morse/{id}``). Representa uma linha
    completa da tabela ``mensagens``, já com o ID primário e o timestamp
    convertido para objeto ``datetime`` nativo do Python.

    Attributes:
        id (int): Chave primária auto-incrementada da tabela ``mensagens``.
        device_id (str): Identificador do dispositivo de origem.
        morse (str): Sequência Morse armazenada.
        text (str): Texto descodificado armazenado.
        timestamp (datetime): Instante de inserção como objeto ``datetime``
            Python, ao contrário do ``int`` de ``MorseEvent`` e do ``str``
            de ``MorseMessage`` — o Pydantic serializa automaticamente para
            ISO 8601 nas respostas JSON.
    """

    id: int
    device_id: str
    morse: str
    text: str
    # O timestamp é datetime aqui (e não int nem str) porque o valor lido da
    # base de dados MySQL já é um objeto datetime Python, e o Pydantic trata
    # da sua serialização para string ISO 8601 na resposta JSON.
    timestamp: datetime