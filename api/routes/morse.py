# =============================================================
#  SoundBridge – Morse Routes
#  Path: api/routes/morse.py
#  API endpoints for Morse message handling
# =============================================================
"""
Router HTTP para os endpoints de processamento de mensagens Morse.

Este módulo define todos os endpoints da API SoundBridge e orquestra o dispatch
de eventos entre a camada de serviços e o repositório de base de dados.
Os endpoints definidos são:

- ``POST /morse`` — recebe eventos individuais do ESP32 (formato novo) ou
  payloads completos de palavras (formato legado); auto-deteta o formato.
- ``GET /morse`` — lista mensagens armazenadas com paginação.
- ``GET /morse/latest`` — devolve a mensagem mais recente (optimizado para
  polling a partir do ESP32).
- ``GET /morse/{message_id}`` — devolve uma mensagem específica por ID.
- ``GET /health`` — sonda de liveness para monitorização.

O padrão de dispatch consiste em detetar o formato do payload pela presença do
campo ``type`` e encaminhar o processamento para o ``DeviceService`` (eventos
em tempo real) ou diretamente para o ``MorseRepository`` (payload legado).
"""

import logging
from datetime import datetime
from typing import Dict, Any, List

from fastapi import APIRouter, HTTPException, status

from api.models.morse import MorseEvent, MorseMessage, MorseRecord
from api.services.device_service import DeviceService
from api.db.repository import MorseRepository

logger = logging.getLogger(__name__)

# Cria o router que será registado na instância FastAPI em main.py.
router = APIRouter()

# device_service e repository são instanciados ao nível do módulo (singletons).
# Isto garante que o estado da máquina de estados (DeviceService._device_states)
# é partilhado entre todos os pedidos HTTP processados pelo mesmo processo,
# o que é necessário para manter a continuidade do estado por dispositivo
# ao longo de múltiplos eventos. Em ambientes multi-processo (ex: Gunicorn com
# vários workers) cada processo terá o seu próprio estado independente.
device_service = DeviceService()
repository = MorseRepository()


@router.post(
    "/morse",
    status_code=status.HTTP_201_CREATED,
    summary="Receive event or legacy word payload",
)
def receive_morse(payload: Dict[str, Any]):
    """Recebe e processa um evento Morse ou um payload de palavra legada.

    Este endpoint aceita dois formatos distintos, auto-detetados pela presença
    do campo ``type`` no payload JSON:

    **Formato novo (ESP32 atualizado):** o payload contém ``type`` com valor
    ``"signal"``, ``"letter_end"`` ou ``"word_end"``. O evento é encaminhado
    para o ``DeviceService`` que mantém a máquina de estados por dispositivo.
    Apenas os eventos ``"word_end"`` resultam em persistência na base de dados;
    os eventos ``"signal"`` e ``"letter_end"`` atualizam apenas o estado em
    memória. Resposta: ``{"status": "processed"}``.

    **Formato legado (firmware antigo):** o payload contém ``morse``, ``text``
    e ``timestamp`` (ISO 8601), sem o campo ``type``. O registo é persistido
    diretamente no repositório, contornando a máquina de estados.
    Resposta: ``{"id": <novo_id>, "status": "stored"}``.

    Args:
        payload (Dict[str, Any]): Corpo do pedido HTTP como dicionário genérico.
            A validação Pydantic é feita manualmente dentro da função para
            permitir a deteção de formato antes de instanciar o modelo correto,
            em vez de usar type hints no parâmetro (que forçariam um único esquema).

    Returns:
        dict: ``{"status": "processed"}`` para o formato novo, ou
            ``{"id": int, "status": "stored"}`` para o formato legado.

    Raises:
        HTTPException: 422 se o payload não for válido para nenhum dos dois formatos.
    """
    # A deteção de formato é feita pela presença do campo "type":
    # o firmware novo envia sempre este campo; o firmware legado nunca o envia.
    if "type" in payload:
        # FORMATO NOVO: evento individual do ESP32
        # MorseEvent é instanciada manualmente (em vez de type hint no parâmetro)
        # para que a deteção de formato acima possa ocorrer antes da validação.
        try:
            event = MorseEvent(**payload)
        except Exception as exc:
            logger.error("Invalid event payload: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid event format: {exc}",
            ) from exc

        logger.debug(
            "[%s] Received event: type='%s'  value='%s'",
            event.device_id, event.type, event.value
        )

        # Obtém (ou cria lazily) o estado da máquina de estados para este dispositivo.
        state = device_service.get_device_state(event.device_id)

        # Dispatch condicional pelo tipo de evento: cada tipo corresponde a uma
        # transição diferente na máquina de estados do dispositivo.
        if event.type == "signal":
            # Só processa o sinal se o valor não for None — garante que um evento
            # "signal" sem valor associado não corrompe o buffer da letra em curso.
            if event.value:
                device_service.process_signal(state, event.value)
        elif event.type == "letter_end":
            device_service.process_letter_end(state)
        elif event.type == "word_end":
            result = device_service.process_word_end(state)
            if result:
                morse_str, text_str = result
                # Só persiste na base de dados em "word_end" e apenas se o
                # resultado não for None (palavra vazia é descartada silenciosamente).
                # Eventos "signal" e "letter_end" atualizam apenas o estado em
                # memória — a persistência nestes pontos seria prematura pois a
                # palavra ainda não está completa.
                repository.insert_word(event.device_id, morse_str, text_str)
        else:
            logger.warning(
                "[%s] Unknown event type '%s' – ignored.",
                event.device_id, event.type
            )

        return {"status": "processed"}

    else:
        # FORMATO LEGADO: payload completo com morse, text e timestamp
        # MorseMessage é instanciada manualmente pelo mesmo motivo que MorseEvent.
        try:
            msg = MorseMessage(**payload)
        except Exception as exc:
            logger.error("Invalid legacy payload: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid payload format: {exc}",
            ) from exc

        # O timestamp do payload legado chega como string ISO 8601 e tem de ser
        # convertido para datetime antes de ser passado ao repositório, que espera
        # um objeto datetime nativo do Python para a inserção MySQL.
        try:
            dt = datetime.fromisoformat(msg.timestamp)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid timestamp format: {exc}",
            ) from exc

        logger.info(
            "[%s] POST /morse (legacy) │ text='%s'  morse='%s'",
            msg.device_id, msg.text, msg.morse,
        )

        # Persiste diretamente no repositório, contornando a máquina de estados,
        # pois o payload legado já contém a palavra completa e descodificada.
        new_id = repository.insert_word(msg.device_id, msg.morse, msg.text, dt)

        return {"id": new_id, "status": "stored"}


@router.get(
    "/morse",
    response_model=List[MorseRecord],
    summary="List all stored messages",
)
def list_morse(limit: int = 100, offset: int = 0):
    """Lista as mensagens armazenadas com suporte a paginação.

    Devolve até ``limit`` registos ordenados do mais recente para o mais antigo.
    Os parâmetros ``limit`` e ``offset`` permitem paginar os resultados: por
    exemplo, a segunda página de 20 resultados usa ``limit=20&offset=20``.

    Args:
        limit (int, optional): Número máximo de registos a devolver.
            Por defeito ``100``.
        offset (int, optional): Número de registos a saltar antes de devolver
            resultados. Por defeito ``0``.

    Returns:
        List[MorseRecord]: Lista de registos validados pelo modelo Pydantic
            ``MorseRecord``.
    """
    rows = repository.get_all_messages(limit=limit, offset=offset)
    return rows

# NOTA: Este endpoint (/morse/latest) está definido ANTES de /morse/{message_id}
# de forma intencional. Se a ordem fosse invertida, o FastAPI tentaria interpretar
# a string literal "latest" como um inteiro no parâmetro message_id e devolveria
# um erro de validação 422 antes de chegar a este handler.
@router.get(
    "/morse/latest",
    summary="Return the most recently inserted message",
)
def get_latest_morse():
    """Devolve o registo inserido mais recentemente na tabela de mensagens.

    Concebido para polling eficiente a partir do ESP32 ou de clientes com
    capacidade de parsing JSON limitada. A decisão de devolver
    ``{"status": "empty"}`` com HTTP 200 em vez de HTTP 404 quando a tabela
    está vazia é intencional: simplifica o tratamento no firmware do ESP32,
    que pode verificar o campo ``status`` sem ter de distinguir códigos HTTP
    de erro de códigos de sucesso.

    Returns:
        dict: O registo mais recente como dicionário, ou ``{"status": "empty"}``
            se a tabela ``mensagens`` estiver vazia.
    """
    row = repository.get_latest_message()

    if row is None:
        logger.info("GET /morse/latest → empty table.")
        return {"status": "empty"}

    logger.info(
        "GET /morse/latest → id=%d  device='%s'  text='%s'",
        row["id"], row["device_id"], row["text"],
    )
    return row


@router.get(
    "/morse/{message_id}",
    response_model=MorseRecord,
    summary="Retrieve a single message by ID",
)
def get_morse(message_id: int):
    """Devolve uma mensagem específica pela sua chave primária.

    Args:
        message_id (int): ID primário da mensagem a recuperar.

    Returns:
        MorseRecord: O registo encontrado, serializado pelo modelo Pydantic.

    Raises:
        HTTPException: 404 se não existir nenhum registo com o ID fornecido.
    """
    row = repository.get_message_by_id(message_id)

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found."
        )

    return row


@router.get("/health", summary="Liveness probe")
def health():
    """Sonda de liveness para verificar que o processo da API está ativo.

    Não verifica a disponibilidade da base de dados — para esse fim deve ser
    usado um endpoint de readiness separado. Destinado a balanceadores de carga
    e sistemas de monitorização que necessitem confirmar que o processo FastAPI
    responde a pedidos HTTP.

    Returns:
        dict: ``{"status": "ok"}`` se o processo estiver ativo.
    """
    return {"status": "ok"}