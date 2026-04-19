##
# @file        api_client.py
# @path        gateway/api_client.py
# @brief       Envia eventos brutos do ESP32 para o backend
#              FastAPI via HTTP POST com lógica de retry.
#
# @details     Este módulo envolve (wraps) ``requests.Session`` para publicar eventos no endpoint REST configurado.
#              Reutiliza uma única sessão HTTP durante todo o ciclo de vida do cliente, evitando o overhead de um novo
#              handshake TCP em cada pedido. Em caso de falha, repete o pedido até ao número máximo de tentativas
#              configurado, aguardando um intervalo fixo entre elas.
#              Não efectua qualquer descodificação Morse nem interpretação semântica dos eventos – esses processos
#              ocorrem exclusivamente no backend. Posiciona-se como o último elo do gateway na cadeia de dados:
#              SerialReader → main.py → ApiClient → API backend.
#
# @dependencies  gateway.config
#
# @limitations   Se todas as tentativas falharem, o evento é descartado de forma silenciosa – não existe fila
#                de espera, persistência local nem mecanismo de dead-letter. Eventos chegados enquanto o cliente
#                aguarda entre tentativas são lidos sequencialmente;
#                não existe paralelismo nem buffer.
##

import logging
import time

import requests

from gateway import config

logger = logging.getLogger(__name__)


class ApiClient:
    """
    Envolve ``requests.Session`` para publicar eventos brutos
    do ESP32 no endpoint REST configurado.

    Esta classe gere o ciclo de vida da sessão HTTP e a lógica
    de retry. Não interpreta o conteúdo dos eventos – limita-se
    a serializá-los como JSON e a enviá-los para a URL configurada.

    @note    ``self._session`` é a única instância de
             ``requests.Session`` e é partilhada por todas as
             chamadas a ``send_event()``.

    DESIGN:  A sessão HTTP é criada uma única vez em ``__init__``
             e reutilizada em todas as chamadas a ``send_event()``,
             em vez de ser recriada a cada pedido. Isto permite a
             reutilização de ligações TCP (keep-alive), reduzindo
             latência e overhead de handshake.

    Exemplo de utilização (gestor de contexto – recomendado)::

        with ApiClient() as api:
            sucesso = api.send_event("signal", value=".")
            if not sucesso:
                print("Evento perdido – todas as tentativas falharam")
    """

    def __init__(
        self,
        url: str            = config.API_URL,
        timeout: int        = config.API_TIMEOUT,
        retries: int        = config.API_RETRIES,
        retry_delay: float  = config.API_RETRY_DELAY,
        device_id: str      = config.DEVICE_ID,
    ) -> None:
        """
        Inicializa o cliente e cria a sessão HTTP persistente.

        @param url          URL completa do endpoint REST para onde
                            os eventos serão enviados.
        @param timeout      Tempo máximo de espera (em segundos) por
                            resposta em cada tentativa de POST.
        @param retries      Número máximo de tentativas por evento
                            antes de desistir e devolver ``False``.
        @param retry_delay  Segundos de espera entre tentativas
                            consecutivas (não aplicado após a última).
        @param device_id    Identificador do dispositivo incluído em
                            cada payload, permitindo ao backend
                            distinguir múltiplas origens.

        DESIGN:     A ``requests.Session`` é criada aqui, uma única
                    vez por instância de ``ApiClient``, e não dentro
                    de ``send_event()``. Criar uma nova sessão por
                    pedido implicaria um novo handshake TCP e TLS em
                    cada POST, aumentando significativamente a latência.
                    Com sessão persistente, o TCP keep-alive reutiliza
                    a ligação estabelecida enquanto o servidor a mantiver
                    activa.

        COUPLING:   Os valores por defeito dos cinco parâmetros provêm
                    directamente de ``gateway.config``; alterar as
                    constantes nesse ficheiro modifica o comportamento
                    de todas as instâncias de ``ApiClient`` criadas
                    sem argumentos explícitos.
        """
        self.url         = url
        self.timeout     = timeout
        self.retries     = retries
        self.retry_delay = retry_delay
        self.device_id   = device_id

        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    # ── Interface pública ─────────────────────────────────────

    def send_event(self, event_type: str, value: str | None = None, timestamp: int | None = None) -> bool:
        """
        Envia um evento bruto do ESP32 para a API via HTTP POST.

        Constrói o payload, tenta o POST até ``self.retries`` vezes
        e retorna o resultado. Nunca lança excepções – todos os erros
        são registados internamente.

        @param event_type  Tipo de evento: ``"signal"``, ``"letter_end"``,
                           ``"word_end"`` ou ``"system"``.
        @param value       Valor associado ao evento (ex.: ``"."`` ou
                           ``"-"`` para eventos ``"signal"``).
                           ``None`` se não aplicável.
        @param timestamp   Marca temporal fornecida pelo ESP32.
                           ``None`` se o ESP32 não incluir este campo.

        @return  ``True`` se a API respondeu com HTTP 2xx em alguma
                 das tentativas; ``False`` se todas as tentativas
                 falharam.

        NOTE:       Um retorno ``False`` significa perda permanente e
                    irrecuperável do evento. O evento não é guardado
                    localmente, não é colocado em fila e não é reenviado
                    em ciclos futuros.

        LIMITATION: Não existe fila de espera (queue), persistência
                    local nem dead-letter mechanism. Se o backend estiver
                    indisponível durante ``retries`` tentativas
                    consecutivas, os dados são perdidos sem hipótese de
                    recuperação.

        DESIGN:     O ciclo de retry percorre as tentativas de 1 a
                    ``self.retries`` (inclusive). A espera entre
                    tentativas (``retry_delay``) é omitida após a última
                    tentativa – não faz sentido aguardar quando não
                    haverá mais tentativas e o chamador já ficou bloqueado
                    tempo suficiente. Esta optimização reduz a latência
                    percebida em caso de falha total.

        COUPLING:   O número de tentativas e o intervalo de espera são
                    lidos de ``self.retries`` e ``self.retry_delay``,
                    que por defeito provêm de ``config.API_RETRIES`` e
                    ``config.API_RETRY_DELAY``.
        """
        payload = {
            "device_id": self.device_id,
            "type": event_type,
        }
        
        if value is not None:
            payload["value"] = value
        
        if timestamp is not None:
            payload["timestamp"] = timestamp

        logger.info("→ API | type='%s'  value='%s'", event_type, value or "")

        for attempt in range(1, self.retries + 1):
            try:
                # json=payload serializa o dicionário como JSON e define
                # Content-Type: application/json automaticamente; usar
                # data=payload enviaria os dados como form-encoded,
                # incompatível com a API FastAPI que espera JSON no corpo.
                resp = self._session.post(self.url, json=payload, timeout=self.timeout)
                # raise_for_status() lança HTTPError para qualquer resposta
                # 4xx ou 5xx, permitindo tratá-las no bloco except abaixo
                # em vez de verificar resp.status_code manualmente.
                resp.raise_for_status()
                logger.info("API aceitou (HTTP %d) na tentativa %d.", resp.status_code, attempt)
                return True

            except requests.exceptions.ConnectionError as exc:
                logger.warning("Tentativa %d/%d – erro de ligação: %s", attempt, self.retries, exc)

            except requests.exceptions.Timeout:
                logger.warning(
                    "Tentativa %d/%d – timeout após %ds.", attempt, self.retries, self.timeout
                )

            except requests.exceptions.HTTPError as exc:
                logger.error("Tentativa %d/%d – erro HTTP: %s", attempt, self.retries, exc)

            except requests.exceptions.RequestException as exc:
                logger.error("Tentativa %d/%d – pedido falhou: %s", attempt, self.retries, exc)

            # Aguarda antes da próxima tentativa (omite espera na última tentativa)
            if attempt < self.retries:
                logger.info("Nova tentativa em %gs…", self.retry_delay)
                time.sleep(self.retry_delay)

        logger.error(
            "Todas as %d tentativa(s) falharam para o evento '%s' – dados perdidos.",
            self.retries,
            event_type,
        )
        return False

    def close(self) -> None:
        """
        Liberta a sessão HTTP subjacente.

        Deve ser chamado quando o cliente já não for necessário,
        para fechar quaisquer ligações TCP persistentes abertas.
        Quando usado como gestor de contexto, este método é
        invocado automaticamente por ``__exit__``.

        @return  None.
        """
        self._session.close()

    # ── Gestor de contexto ────────────────────────────────────

    def __enter__(self) -> "ApiClient":
        """
        Retorna a instância para uso no bloco ``with``.

        O recurso (sessão HTTP) já foi adquirido em ``__init__``,
        pelo que este método apenas retorna ``self``.

        @return  A própria instância, pronta a utilizar.

        DESIGN:  O padrão de gestor de contexto garante que
                 ``close()`` é sempre invocado ao sair do bloco
                 ``with``, libertando as ligações TCP mesmo em
                 caso de excepção no código chamador.
        """
        return self

    def __exit__(self, *_) -> None:
        """
        Fecha a sessão HTTP ao sair do bloco ``with``.

        @param _  Informação sobre excepção (tipo, valor, traceback);
                  ignorada – qualquer excepção propaga-se normalmente.

        @return   None. Não suprime excepções.

        DESIGN:  Delega em ``close()`` para centralizar a lógica de
                 fecho num único método, evitando duplicação entre o
                 gestor de contexto e chamadas directas.

        NOTE:    Se ``__exit__`` for chamado sobre uma sessão já
                 fechada (ex.: após chamada explícita a ``close()``
                 antes de sair do bloco ``with``), ``requests.Session``
                 trata este caso silenciosamente – não lança excepção.
        """
        self.close()