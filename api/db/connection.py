# =============================================================
#  SoundBridge – Database Connection
#  Path: api/db/connection.py
#  MySQL connection pool management and lifespan
# =============================================================

import logging
from contextlib import asynccontextmanager

import mysql.connector
import mysql.connector.pooling
from fastapi import FastAPI, HTTPException, status

from api.core.config import DatabaseConfig

logger = logging.getLogger(__name__)


# Module-level pool reference (initialized inside lifespan)
_pool: mysql.connector.pooling.MySQLConnectionPool | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Create the MySQL connection pool at startup; close it on shutdown.
    
    This function is used as the FastAPI lifespan context manager.
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
        # App will start but every DB call will fail gracefully

    yield  # ← application runs here

    _pool = None
    logger.info("MySQL pool released.")


def get_connection() -> mysql.connector.pooling.PooledMySQLConnection:
    """
    Return a connection from the pool.
    
    Returns
    -------
    mysql.connector.pooling.PooledMySQLConnection
        A pooled MySQL connection
        
    Raises
    ------
    HTTPException
        503 if the pool is unavailable or connection cannot be obtained
    """
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
    """
    Get the connection pool instance (for testing/debugging).
    
    Returns
    -------
    mysql.connector.pooling.MySQLConnectionPool | None
        The connection pool or None if not initialized
    """
    return _pool