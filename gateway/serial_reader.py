##
# @file        serial_reader.py
# @path        gateway/serial_reader.py
# @brief       Gere a ligação USB série ao ESP32 e devolve
#              mensagens JSON já processadas.
#
# @details     Este módulo envolve (wraps) a biblioteca pyserial para abrir a porta série configurada, ler uma linha
#              de cada vez e tentar interpretar essa linha como JSON.
#              Não efectua qualquer interpretação do conteúdo das mensagens – essa responsabilidade pertence ao main.py
#              e, em última instância, à API backend.
#              Posiciona-se como o primeiro elo da cadeia de dados:
#              ESP32 → SerialReader → main.py → ApiClient → API.
#              Em caso de erro de leitura ou desconexão da porta, reconecta-se automaticamente de forma bloqueante,
#              interrompendo o fluxo de eventos até o hardware estar novamente disponível.
#
# @dependencies  gateway.config
#
# @limitations   A reconexão é bloqueante: enquanto a porta não abrir, nenhum evento é lido nem enviado para a API.
#                Linhas recebidas durante a reconexão são perdidas.
#                Não existe validação dos campos individuais do JSON devolvido – campos em falta ou com tipo errado só
#                serão detectados em main.py.
##

import json
import logging
import time

import serial
import serial.serialutil

from gateway import config

logger = logging.getLogger(__name__)


class SerialReader:
    """
    Envolve uma ligação pyserial e expõe o método ``read_message()``.

    Esta classe é responsável por abrir e fechar a porta série,
    reconectar automaticamente após erros e devolver mensagens JSON
    já processadas como dicionários Python. Não interpreta o conteúdo
    das mensagens – apenas garante que chegam ao chamador de forma fiável.

    @note    A classe implementa o protocolo de gestor de contexto
             (context manager) para garantir que a porta série é sempre
             fechada de forma ordenada, mesmo em caso de excepção.

    @note    ``self._serial`` é a única instância de ``serial.Serial``
             e é criada em ``connect()``. Todos os métodos acedem
             exclusivamente a este atributo para comunicar com o hardware.

    Exemplo de utilização (gestor de contexto – recomendado)::

        with SerialReader() as reader:
            while True:
                msg = reader.read_message()
                if msg:
                    process(msg)
    """

    def __init__(
        self,
        port: str      = config.SERIAL_PORT,
        baudrate: int  = config.BAUDRATE,
        timeout: float = config.SERIAL_TIMEOUT,
    ) -> None:
        """
        Inicializa os parâmetros da ligação série sem abrir a porta.

        A abertura efectiva ocorre em ``connect()`` (ou em ``__enter__``
        quando usado como gestor de contexto).

        @param port      Nome da porta série (ex.: ``"COM3"`` no Windows
                         ou ``"/dev/ttyUSB0"`` no Linux/macOS).
        @param baudrate  Velocidade da ligação em bits por segundo.
                         Deve corresponder à configuração do ESP32.
        @param timeout   Tempo máximo de espera (em segundos) em cada
                         chamada a ``readline()``. Determina a latência
                         de detecção de ausência de dados.

        COUPLING: Os valores por defeito provêm directamente de
                  ``gateway.config``; alterar as constantes nesse
                  ficheiro modifica o comportamento desta classe.
        """
        self.port     = port
        self.baudrate = baudrate
        self.timeout  = timeout
        self._serial: serial.Serial | None = None

    # ── Gestão de ligação ─────────────────────────────────────

    def connect(self) -> None:
        """
        Abre a porta série, bloqueando até conseguir.

        Tenta abrir a porta em ciclo infinito, aguardando 3 segundos
        entre tentativas falhadas.

        @return  None. Retorna apenas após abertura bem-sucedida da porta.

        DESIGN:     O ciclo é infinito por decisão arquitectural. A
                    alternativa (falhar com excepção após N tentativas)
                    obrigaria o chamador a gerir a reconexão, espalhando
                    essa lógica pelo código. Ao manter o ciclo aqui,
                    garante-se que ``connect()`` nunca retorna sem porta
                    aberta – o chamador pode assumir sempre que, após o
                    retorno, a ligação está activa.

        LIMITATION: Enquanto este método estiver em execução, o gateway
                    está completamente bloqueado: nenhum evento é lido,
                    processado ou enviado para a API. Mensagens emitidas
                    pelo ESP32 durante este período são perdidas (o buffer
                    série do SO tem capacidade limitada).
        """
        while True:
            try:
                self._serial = serial.Serial(
                    port=self.port,
                    baudrate=self.baudrate,
                    timeout=self.timeout,
                )
                logger.info("Serial '%s' aberta a %d baud.", self.port, self.baudrate)
                return
            except serial.serialutil.SerialException as exc:
                logger.error("Não foi possível abrir '%s': %s – nova tentativa em 3 s…", self.port, exc)
                time.sleep(3)

    def disconnect(self) -> None:
        """
        Fecha a porta série de forma ordenada.

        É seguro chamar este método mesmo que a porta já esteja
        fechada ou nunca tenha sido aberta.

        @return  None.
        """
        if self._serial and self._serial.is_open:
            self._serial.close()
            logger.info("Serial '%s' fechada.", self.port)

    # ── Leitura ───────────────────────────────────────────────

    def read_message(self) -> dict | None:
        """
        Lê uma linha da porta série e interpreta-a como JSON.

        Em cada chamada, bloqueia até receber uma linha terminada
        em ``\\n`` ou até o timeout expirar. A linha é descodificada
        e interpretada como JSON; em caso de falha é descartada
        silenciosamente.

        @return  Dicionário com os dados da mensagem em caso de sucesso,
                 ou ``None`` em qualquer uma das seguintes situações:

        NOTE:    Condições que causam retorno de ``None``:
                 1. Timeout de ``readline()`` – nenhum dado chegou
                    dentro do intervalo ``SERIAL_TIMEOUT``. É o caso
                    normal de ausência de actividade no ESP32.
                 2. Linha recebida mas vazia após descodificação e
                    remoção de espaços (ex.: linha só com ``\\r\\n``).
                 3. Linha não é JSON válido – registada como debug e
                    descartada. Pode ocorrer no arranque do ESP32 ou
                    em mensagens de diagnóstico em texto simples.
                 4. Erro de porta série (``SerialException``) – a porta
                    é fechada e ``connect()`` é chamado imediatamente
                    (bloqueante). Retorna ``None`` após registar o erro.
                 5. Porta não está aberta no início da chamada – efectua
                    reconexão preventiva e retorna ``None``.

        COUPLING: O comportamento de timeout em ``readline()`` depende
                  directamente de ``config.SERIAL_TIMEOUT``; alterar
                  esse valor modifica a latência de detecção de ausência
                  de dados e a frequência de ciclos ``None`` no loop
                  principal.
        """
        # Verificação de segurança: reconectar se a porta estiver fechada por algum motivo
        if self._serial is None or not self._serial.is_open:
            logger.warning("Porta série não está aberta – a reconectar…")
            self.connect()
            return None

        try:
            raw: bytes = self._serial.readline()   # devolve b"" em caso de timeout
        except serial.serialutil.SerialException as exc:
            logger.error("Erro de leitura série: %s – a reconectar…", exc)
            self.disconnect()
            self.connect()
            return None

        if not raw:
            return None  # timeout normal – nenhum dado disponível neste ciclo

        # errors="ignore" descarta bytes inválidos (ex.: lixo de arranque
        # do ESP32) em vez de lançar UnicodeDecodeError
        line = raw.decode("utf-8", errors="ignore").strip()
        if not line:
            return None

        logger.debug("RAW ← '%s'", line)

        try:
            return json.loads(line)
        except json.JSONDecodeError:
            logger.debug("Não é JSON válido – a descartar: '%s'", line)
            return None

    # ── Gestor de contexto ────────────────────────────────────

    def __enter__(self) -> "SerialReader":
        """
        Abre a porta série e retorna a instância.

        @return  A própria instância, já com a porta aberta.

        DESIGN:  O padrão de gestor de contexto garante que
                 ``disconnect()`` é sempre chamado ao sair do bloco
                 ``with``, mesmo em caso de excepção no código
                 chamador, evitando que a porta fique bloqueada
                 entre reinícios do gateway.
        """
        self.connect()
        return self

    def __exit__(self, *_) -> None:
        """
        Fecha a porta série ao sair do bloco ``with``.

        @param _  Informação sobre excepção (tipo, valor, traceback);
                  ignorada – qualquer excepção propaga-se normalmente.

        @return   None. Não suprime excepções.

        DESIGN:  Delega em ``disconnect()`` para centralizar a lógica
                 de fecho num único método.

        NOTE:    Se ``__exit__`` for chamado sobre uma porta já fechada
                 (ex.: após reconexão forçada por erro de leitura),
                 ``disconnect()`` trata este caso silenciosamente graças
                 à verificação interna de ``is_open``.
        """
        self.disconnect()