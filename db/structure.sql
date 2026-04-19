-- =============================================================
-- @file        schema.sql
-- @path        db/schema.sql
-- @brief       Define o schema da base de dados SoundBridge.
--
-- @dependencies  Servidor MySQL/MariaDB com suporte a InnoDB e utf8mb4.
--
-- @limitations   Não existe soft-delete nem histórico de alterações. A coluna `text` guarda apenas
--                o resultado final da descodificação – a sequência de sinais intermédios (pontos e
--                traços individuais) não é persistida aqui.
-- =============================================================

-- Cria a base de dados se ainda não existir
CREATE DATABASE IF NOT EXISTS soundbridge
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE soundbridge;

-- -------------------------------------------------------------
--  Tabela: mensagens
--  Uma linha por palavra Morse completamente descodificada.
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mensagens (
    id         INT            AUTO_INCREMENT PRIMARY KEY,
    device_id  VARCHAR(50)    NOT NULL,
    morse      TEXT           NOT NULL,
    text       TEXT           NOT NULL,
    timestamp  DATETIME       NOT NULL,

    -- Indexes for the most common query patterns
    INDEX idx_device   (device_id),
    INDEX idx_timestamp(timestamp)
)
ENGINE  = InnoDB
DEFAULT CHARSET = utf8mb4
COLLATE = utf8mb4_unicode_ci;