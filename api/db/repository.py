# =============================================================
#  SoundBridge – Database Repository
#  Path: api/db/repository.py
#  Database operations (CRUD) for Morse messages
# =============================================================
"""
Repositório de acesso à base de dados para mensagens Morse.

Este módulo implementa o padrão Repository, isolando completamente o SQL
do resto da aplicação. Toda a lógica de acesso à base de dados — queries,
gestão de cursores, tratamento de erros e rollback — está encapsulada nesta
camada, garantindo que as camadas superiores (rotas, serviços) nunca interagem
diretamente com o ``mysql.connector``.

A ausência de um ORM é intencional: as queries são simples e o controlo
explícito do SQL facilita a otimização e a auditoria de desempenho.

Depende de: ``api.db.connection.get_connection``.
"""

import logging
from datetime import datetime
from typing import List, Dict, Any

import mysql.connector
from fastapi import HTTPException, status

from api.db.connection import get_connection

logger = logging.getLogger(__name__)


class MorseRepository:
    """Repositório de operações CRUD sobre a tabela ``mensagens``.

    Implementa o padrão Repository: cada método encapsula uma operação de base
    de dados específica, com gestão explícita de conexão, cursor, commit/rollback
    e fecho de recursos no bloco ``finally``.

    Todos os métodos são estáticos — não há estado de instância — o que permite
    usar a classe tanto como singleton (instanciada uma vez no módulo de rotas)
    como diretamente via ``MorseRepository.metodo()``.

    Não utiliza ORM: as queries SQL são escritas explicitamente para manter
    controlo total sobre o desempenho e facilitar auditorias de segurança.
    """

    @staticmethod
    def insert_word(
        device_id: str,
        morse: str,
        text: str,
        timestamp: datetime | None = None
    ) -> int:
        """Insere uma palavra Morse completa na base de dados.

        Chamado após a máquina de estados sinalizar ``word_end`` (formato novo)
        ou diretamente ao receber um payload legado completo. Realiza um commit
        explícito após a inserção e um rollback em caso de erro, garantindo a
        consistência da base de dados.

        Args:
            device_id (str): Identificador do dispositivo ESP32 que enviou a mensagem.
            morse (str): Sequência Morse da palavra, com letras separadas por espaço
                (ex: ``"... --- ..."``) .
            text (str): Texto descodificado correspondente (ex: ``"SOS"``).
            timestamp (datetime | None, optional): Momento da mensagem. Se ``None``,
                usa o instante atual do servidor como fallback, garantindo que o
                registo tem sempre um timestamp válido mesmo que o dispositivo
                não o envie. Por defeito ``None``.

        Returns:
            int: ID auto-incrementado (``lastrowid``) da linha inserida, devolvido
                ao router para inclusão na resposta HTTP.

        Raises:
            HTTPException: 500 se a inserção falhar por erro de base de dados.
        """
        # Usa o instante atual do servidor como fallback quando o dispositivo
        # não fornece timestamp — evita NULLs na coluna e mantém a ordenação
        # temporal consistente mesmo em dispositivos sem relógio sincronizado.
        if timestamp is None:
            timestamp = datetime.now()

        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO mensagens (device_id, morse, text, timestamp)
                VALUES (%s, %s, %s, %s)
                """,
                (device_id, morse, text, timestamp),
            )
            conn.commit()
            # cursor.lastrowid contém o ID gerado pelo AUTO_INCREMENT da tabela,
            # disponível imediatamente após o execute() e antes de fechar o cursor.
            new_id = cursor.lastrowid
            logger.info("[%s] Inserted mensagens.id=%d  text='%s'", device_id, new_id, text)
            return new_id
        except mysql.connector.Error as exc:
            # Em caso de erro, o rollback desfaz qualquer alteração parcial
            # que possa ter ocorrido antes da exceção, mantendo a integridade
            # da transação.
            conn.rollback()
            logger.error("[%s] DB insert failed: %s", device_id, exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database insert failed.",
            ) from exc
        finally:
            # O bloco finally garante que o cursor e a conexão são sempre
            # fechados, devolvendo a conexão ao pool independentemente do
            # resultado da operação.
            cursor.close()
            conn.close()

    @staticmethod
    def get_all_messages(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Obtém múltiplas mensagens da base de dados com suporte a paginação.

        Devolve as mensagens ordenadas da mais recente para a mais antiga,
        o que é o comportamento esperado pelas interfaces de consulta e pelo
        endpoint de listagem.

        Args:
            limit (int, optional): Número máximo de registos a devolver.
                Por defeito ``100``.
            offset (int, optional): Número de registos a saltar, usado para
                paginação (ex: página 2 com limit=10 usa offset=10).
                Por defeito ``0``.

        Returns:
            List[Dict[str, Any]]: Lista de registos da tabela ``mensagens``,
                cada um representado como dicionário com os nomes das colunas
                como chaves.

        Raises:
            HTTPException: 500 se a query falhar por erro de base de dados.
        """
        conn = get_connection()
        # cursor(dictionary=True) faz com que cada linha seja devolvida como
        # dict {coluna: valor} em vez de tuplo, simplificando a serialização
        # para JSON pelo FastAPI e evitando mapeamentos manuais de índices.
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT * FROM mensagens ORDER BY timestamp DESC LIMIT %s OFFSET %s",
                (limit, offset),
            )
            rows = cursor.fetchall()
            return rows
        except mysql.connector.Error as exc:
            logger.error("DB select failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database query failed.",
            ) from exc
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_message_by_id(message_id: int) -> Dict[str, Any] | None:
        """Obtém uma mensagem específica pelo seu ID primário.

        Devolve ``None`` se não existir nenhum registo com o ID fornecido,
        permitindo ao router decidir se deve devolver 404 ou outro código.

        Args:
            message_id (int): Chave primária (``id``) da mensagem a recuperar.

        Returns:
            Dict[str, Any] | None: Registo da mensagem como dicionário,
                ou ``None`` se não encontrado.

        Raises:
            HTTPException: 500 se a query falhar por erro de base de dados.
        """
        conn = get_connection()
        # cursor(dictionary=True) para consistência com os restantes métodos
        # e compatibilidade direta com o modelo Pydantic MorseRecord.
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM mensagens WHERE id = %s", (message_id,))
            row = cursor.fetchone()
            return row
        except mysql.connector.Error as exc:
            logger.error("DB select by id failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database query failed.",
            ) from exc
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_latest_message() -> Dict[str, Any] | None:
        """Obtém a mensagem inserida mais recentemente.

        Utiliza ``ORDER BY timestamp DESC LIMIT 1`` para garantir que é sempre
        devolvida a mensagem com o timestamp mais recente, independentemente da
        ordem de inserção física na tabela (que pode divergir em caso de
        inserções concorrentes com timestamps explícitos).

        Returns:
            Dict[str, Any] | None: O registo mais recente da tabela ``mensagens``
                como dicionário, ou ``None`` se a tabela estiver vazia.

        Raises:
            HTTPException: 500 se a query falhar por erro de base de dados.
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            # ORDER BY timestamp DESC garante que se obtém a mensagem mais recente
            # mesmo que o id auto-incrementado não corresponda à ordem temporal
            # (ex: inserções legadas com timestamps históricos).
            # LIMIT 1 limita a leitura a uma única linha, otimizando a query.
            cursor.execute(
                "SELECT * FROM mensagens ORDER BY timestamp DESC LIMIT 1"
            )
            row = cursor.fetchone()
            return row
        except mysql.connector.Error as exc:
            logger.error("DB select latest failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database query failed.",
            ) from exc
        finally:
            cursor.close()
            conn.close()