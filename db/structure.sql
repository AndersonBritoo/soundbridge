-- =============================================================
--  SoundBridge – Database Schema
-- =============================================================

-- Create the database if it does not exist yet
CREATE DATABASE IF NOT EXISTS soundbridge
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE soundbridge;

-- Messages table – one row per decoded Morse word
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