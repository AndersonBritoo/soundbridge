# =============================================================
#  SoundBridge – Database Connection
#  Path: api/db/connection.py
#  MySQL connection pool management and lifespan
# =============================================================
"""
Gestão do pool de conexões MySQL e lifespan da aplicação FastAPI.

Este módulo é responsável por criar e destruir o pool de conexões MySQL em
sincronização com o ciclo de vida da aplicação FastAPI, através do mecanismo
``lifespan``. Expõe também funções utilitárias para obter conexões individuais
a partir do pool e para inspecionar o estado do pool (útil em testes).

Depende de: ``mysql.connector``, ``api.core.config.DatabaseConfig``.
"""

import logging
from contextlib import asynccontextmanager

import mysql.connector
import mysql.connector.pooling
from fastapi import FastAPI, HTTPException, status

from api.core.config import DatabaseConfig

logger = logging.getLogger(__name__)


# Referência global ao pool de conexões, inicializada a None.
# É preenchida durante o startup da aplicação e reposta a None no shutdown.
# O facto de ser uma variável de módulo garante que existe um único pool
# partilhado por todos os pedidos HTTP ao longo do tempo de vida do processo.
_pool: mysql.connector.pooling.MySQLConnectionPool | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gere o ciclo de vida do pool de conexões MySQL.

    Utiliza o padrão ``asynccontextmanager`` exigido pelo FastAPI para o
    parâmetro ``lifespan``. A função é declarada ``async`` por imposição da
    interface FastAPI, embora a criação do pool seja uma operação síncrona —
    o ``mysql.connector`` não suporta operações assíncronas nativas.

    O bloco antes do ``yield`` corresponde ao startup: tenta criar o pool.
    O bloco após o ``yield`` corresponde ao shutdown: liberta a referência ao pool.

    Em caso de falha no startup (ex: MySQL inacessível), a aplicação arranca
    na mesma mas todas as chamadas à base de dados falharão com HTTP 503,
    permitindo que o processo fique ativo e recupere quando a base de dados
    ficar disponível.

    Args:
        app (FastAPI): Instância da aplicação FastAPI (exigida pela interface
            de lifespan, não utilizada diretamente nesta função).
    """
    global _pool
    try:
        _pool = mysql.connector.pooling.MySQLConnectionPool(
            pool_name="soundbridge_pool",
            pool_size=DatabaseConfig.POOL_SIZE,
            **DatabaseConfig.get_config(),
        )
        logger.info("MySQL connection pool created (size=%d).", DatabaseConfig.POOL_SIZE)
    except mysql.connector.Error as exc:
        logger.error("Cannot create MySQL pool: %s", exc)
        # A aplicação arranca mesmo sem pool disponível — cada pedido que necessite
        # de base de dados receberá um erro 503 em vez de bloquear o startup.
        # App will start but every DB call will fail gracefully

    # O yield separa o código de startup do código de shutdown.
    # A aplicação fica em execução enquanto o contexto está suspenso aqui.
    yield  # ← application runs here

    # No shutdown, repõe a referência a None em vez de chamar pool.close()
    # explicitamente, porque o mysql.connector gere internamente o fecho das
    # conexões quando o objeto é recolhido pelo garbage collector.
    _pool = None
    logger.info("MySQL pool released.")


def get_connection() -> mysql.connector.pooling.PooledMySQLConnection:
    """Obtém uma conexão disponível a partir do pool.

    Deve ser chamada no início de cada operação de base de dados e a conexão
    obtida deve ser devolvida ao pool (via ``conn.close()``) no bloco ``finally``
    após o uso, para não esgotar o pool sob carga.

    Returns:
        mysql.connector.pooling.PooledMySQLConnection: Conexão ativa retirada
            do pool, pronta para executar queries.

    Raises:
        HTTPException: 503 se o pool não estiver inicializado (MySQL indisponível
            no startup) ou se não for possível obter uma conexão (pool esgotado
            ou erro de rede).
    """
    # Verifica se o pool foi inicializado antes de tentar obter uma conexão.
    # Se estiver a None, a aplicação arrancou mas o MySQL não estava acessível —
    # devolve 503 para sinalizar indisponibilidade temporária ao cliente.
    if _pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database pool not initialised.",
        )
    try:
        return _pool.get_connection()
    except mysql.connector.Error as exc:
        logger.error("Pool connection error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable.",
        ) from exc


def get_pool() -> mysql.connector.pooling.MySQLConnectionPool | None:
    """Devolve a instância atual do pool de conexões.

    Destinada a uso em testes e ferramentas de diagnóstico, permitindo inspecionar
    o estado do pool sem expor a variável de módulo ``_pool`` diretamente.

    Returns:
        mysql.connector.pooling.MySQLConnectionPool | None: O pool ativo, ou
            ``None`` se o pool ainda não foi inicializado ou já foi libertado.
    """
    return _pool