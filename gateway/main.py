#!/usr/bin/env python3
##
# @file        main.py
# @path        gateway/main.py
# @brief       Ponto de entrada do gateway SoundBridge; lê
#              eventos do ESP32 e encaminha-os para a API REST.
#
# @details     Este módulo contém o ciclo de execução principal (loop infinito) do gateway. Instancia ``SerialReader``
#              e ``ApiClient`` como gestores de contexto, lê uma mensagem de cada vez e decide se a encaminha para a
#              API ou a processa localmente. Eventos do tipo ``"system"`` são registados localmente e nunca
#              enviados. Todos os outros tipos de evento são encaminhados para a API sem transformação. Toda a
#              descodificação Morse ocorre no backend – este módulo actua apenas como bridge transparente. Posiciona-se
#              no centro da cadeia de dados:
#              SerialReader → main.py → ApiClient → API backend.
#
# @dependencies  gateway.config, gateway.serial_reader,
#                gateway.api_client
#
# @limitations   Não existe buffer nem paralelismo: enquanto ``send_event()`` aguarda entre tentativas de retry,
#                as mensagens chegadas pela porta série são lidas sequencialmente no próximo ciclo (ou perdidas se
#                o buffer do SO estiver cheio). Eventos com campo ``"type"`` ausente são ignorados com aviso no log.
##

import logging
import sys
import time

# sys.path.insert garante que o pacote gateway é encontrado quando
# o script é executado directamente (python gateway/main.py) e não
# como módulo instalado; sem esta linha os imports relativos falhariam.
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gateway.config        import LOG_LEVEL, LOG_FORMAT, LOG_DATE_FORMAT
from gateway.serial_reader import SerialReader
from gateway.api_client    import ApiClient


def _configure_logging() -> None:
    """
    Inicializa o logger raiz com os valores definidos em config.

    @return  None.

    COUPLING: LOG_LEVEL, LOG_FORMAT e LOG_DATE_FORMAT são importados
              directamente de ``gateway.config``; alterar essas
              constantes modifica o comportamento do registo em todo
              o gateway.
    """
    # getattr(logging, LOG_LEVEL.upper(), logging.DEBUG) converte a
    # string de configuração (ex.: "INFO") na constante inteira
    # correspondente do módulo logging (ex.: logging.INFO = 20).
    # O terceiro argumento (logging.DEBUG) é o fallback para strings
    # desconhecidas que não correspondam a nenhum nível válido.
    level = getattr(logging, LOG_LEVEL.upper(), logging.DEBUG)
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
        stream=sys.stdout,
    )


def run() -> None:
    """
    Ciclo principal – lê mensagens do ESP32 e encaminha-as para a API.

    Inicializa o logging, instancia os dois subsistemas como gestores
    de contexto e entra num ciclo infinito. Em cada iteração tenta ler
    uma mensagem da porta série; se obtiver uma mensagem válida, filtra
    eventos ``"system"`` e encaminha os restantes para a API.

    @return  None. Retorna apenas após ``KeyboardInterrupt`` (Ctrl-C).

    DESIGN:     O ciclo captura ``Exception`` de forma genérica
                (bare Exception) para garantir que nenhuma excepção
                inesperada termina o gateway. A filosofia é que um
                gateway de IoT deve ser "indestrutível" em produção:
                erros transitórios não devem exigir reinício manual.
                A excepção é registada com traceback completo e o
                ciclo retoma após 1 segundo. ``KeyboardInterrupt``
                não é capturado por ``Exception`` e propaga-se
                normalmente, permitindo paragem limpa com Ctrl-C.

    NOTE:       Quando ``read_message()`` retorna ``None`` (timeout
                normal sem dados), o ciclo dorme 0,01 segundos antes
                de continuar. Este sleep evita busy-waiting puro
                (ciclo a 100 % de CPU) quando o ESP32 não está a
                enviar dados, cedendo o processador ao SO sem
                introduzir latência perceptível na leitura de eventos
                reais.

    NOTE:       Eventos com ``event_type == "system"`` são consumidos
                localmente: o campo ``"message"`` é registado no log
                e o ciclo avança sem chamar ``api.send_event()``.
                Estes eventos são diagnósticos internos do ESP32 (ex.:
                arranque, estado de memória) sem relevância para o
                backend de descodificação Morse.

    LIMITATION: Não existe buffer nem processamento paralelo. Os
                eventos chegados durante os intervalos de retry do
                ``ApiClient`` são lidos sequencialmente quando o ciclo
                retomar; se o buffer série do SO estiver cheio, esses
                eventos são perdidos sem notificação.
    """
    _configure_logging()
    logger = logging.getLogger(__name__)

    logger.info("=" * 56)
    logger.info("  SoundBridge Gateway  –  a iniciar (modo bridge)")
    logger.info("=" * 56)

    with SerialReader() as reader, ApiClient() as api:
        logger.info("A escutar em '%s'…  (Ctrl-C para parar)", reader.port)

        while True:
            try:
                message = reader.read_message()

                if message is None:
                    # Nenhum dado neste ciclo – cede o CPU brevemente
                    # para evitar busy-waiting a 100 %
                    time.sleep(0.01)
                    continue

                logger.debug("MSG ← %s", message)

                # Extrai os campos do evento recebido pelo ESP32
                event_type = message.get("type")
                value = message.get("value")
                timestamp = message.get("timestamp")

                # Mensagens "system" são tratadas localmente e nunca
                # encaminhadas para a API – são diagnósticos internos
                # do ESP32 sem valor para o backend Morse
                if event_type == "system":
                    logger.info("ESP32: %s", message.get("message"))
                    continue

                # Encaminha todos os outros eventos directamente para a API
                if event_type:
                    api.send_event(event_type=event_type, value=value, timestamp=timestamp)
                else:
                    logger.warning("Mensagem sem campo 'type' – ignorada: %s", message)

            except KeyboardInterrupt:
                logger.info("Interrompido pelo utilizador – a terminar.")
                break

            except Exception as exc:             # noqa: BLE001
                # Captura qualquer excepção inesperada para manter o loop
                # vivo; regista com traceback completo e aguarda 1 s antes
                # de retomar
                logger.exception("Excepção não tratada: %s – a retomar em 1 s…", exc)
                time.sleep(1)

    logger.info("Gateway parado.")


if __name__ == "__main__":
    run()