# =============================================================
#  SoundBridge – Database Repository
#  Path: api/db/repository.py
#  Database operations (CRUD) for Morse messages
# =============================================================

import logging
from datetime import datetime
from typing import List, Dict, Any

import mysql.connector
from fastapi import HTTPException, status

from api.db.connection import get_connection

logger = logging.getLogger(__name__)


class MorseRepository:
    """Repository for Morse message database operations."""
    
    @staticmethod
    def insert_word(
        device_id: str,
        morse: str,
        text: str,
        timestamp: datetime | None = None
    ) -> int:
        """
        Insert a completed Morse word into the database.
        
        Parameters
        ----------
        device_id : str
            Device identifier
        morse : str
            Morse code sequence (space-separated)
        text : str
            Decoded text
        timestamp : datetime | None
            Timestamp for the message (defaults to now)
            
        Returns
        -------
        int
            The new row ID
            
        Raises
        ------
        HTTPException
            500 if database insert fails
        """
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
            new_id = cursor.lastrowid
            logger.info("[%s] Inserted mensagens.id=%d  text='%s'", device_id, new_id, text)
            return new_id
        except mysql.connector.Error as exc:
            conn.rollback()
            logger.error("[%s] DB insert failed: %s", device_id, exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database insert failed.",
            ) from exc
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def get_all_messages(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Retrieve multiple messages from the database.
        
        Parameters
        ----------
        limit : int
            Maximum number of rows to return (default: 100)
        offset : int
            Number of rows to skip (default: 0)
            
        Returns
        -------
        List[Dict[str, Any]]
            List of message records as dictionaries
            
        Raises
        ------
        HTTPException
            500 if database query fails
        """
        conn = get_connection()
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
        """
        Retrieve a single message by its ID.
        
        Parameters
        ----------
        message_id : int
            Primary key of the message
            
        Returns
        -------
        Dict[str, Any] | None
            Message record as dictionary, or None if not found
            
        Raises
        ------
        HTTPException
            500 if database query fails
        """
        conn = get_connection()
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