-- MyDigiDia Record — Database Schema
-- Run this once against a fresh MySQL server to create the database and core tables.
-- The application will automatically add any missing optional columns on first run.

CREATE DATABASE IF NOT EXISTS mydigidia_record
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE mydigidia_record;

-- Core user accounts
CREATE TABLE IF NOT EXISTS users (
    user_id         INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    email           VARCHAR(150) NOT NULL UNIQUE,
    phone           VARCHAR(20)  NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    gender          VARCHAR(20)  NULL,
    date_of_birth   DATE         NULL,
    profile_pic     VARCHAR(255) NULL,
    age             INT          NULL,
    diabetes_type   VARCHAR(50)  NULL,
    emergency_name  VARCHAR(100) NULL,
    emergency_phone VARCHAR(20)  NULL,
    doctor_name     VARCHAR(150) NULL,
    last_login      DATETIME     NULL,
    created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

-- In-app notifications
CREATE TABLE IF NOT EXISTS notifications (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT NOT NULL,
    message     VARCHAR(255) NOT NULL,
    type        VARCHAR(30) DEFAULT 'system',
    is_read     TINYINT(1) DEFAULT 0,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Blood glucose readings
CREATE TABLE IF NOT EXISTS glucose_readings (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT NOT NULL,
    device_id       INT NULL,
    glucose_level   FLOAT NOT NULL,
    reading_time    DATETIME NOT NULL,
    status          VARCHAR(20) DEFAULT 'normal',
    notes           TEXT NULL,
    meal_timing     VARCHAR(50) NULL,
    INDEX idx_user_reading_time (user_id, reading_time),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Per-user application settings
CREATE TABLE IF NOT EXISTS user_settings (
    id                      INT AUTO_INCREMENT PRIMARY KEY,
    user_id                 INT NOT NULL,
    theme                   VARCHAR(20) DEFAULT 'light',
    language                VARCHAR(40) DEFAULT 'English',
    email_notifications     TINYINT(1) DEFAULT 1,
    sms_notifications       TINYINT(1) DEFAULT 0,
    glucose_alerts          TINYINT(1) DEFAULT 1,
    weekly_report           TINYINT(1) DEFAULT 0,
    reminder_notifications  TINYINT(1) DEFAULT 1,
    profile_visibility      TINYINT(1) DEFAULT 0,
    data_sharing            TINYINT(1) DEFAULT 0,
    auto_save               TINYINT(1) DEFAULT 1,
    cloud_sync              TINYINT(1) DEFAULT 0,
    glucose_unit            VARCHAR(20) DEFAULT 'mg/dL',
    reminder_frequency      VARCHAR(30) DEFAULT 'daily',
    emergency_contact       VARCHAR(30) NULL,
    daily_tracking          VARCHAR(20) DEFAULT '4',
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_user_settings (user_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
