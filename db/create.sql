-- Topaz Bot Database Schema
SET NAMES utf8mb4;
SET time_zone = '+00:00';
SET sql_mode = 'STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION';
SET FOREIGN_KEY_CHECKS = 0;
START TRANSACTION;

CREATE TABLE IF NOT EXISTS `users` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `chat_id` BIGINT NOT NULL,
  `username` VARCHAR(64) NULL,
  `email` VARCHAR(255) NULL,
  `receipt_opt_out` TINYINT(1) NOT NULL DEFAULT 0,
  `balance_credits` INT UNSIGNED NOT NULL DEFAULT 0,
  `is_admin` TINYINT(1) NOT NULL DEFAULT 0,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ux_users_chat_id` (`chat_id`),
  KEY `idx_users_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `payments` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT UNSIGNED NOT NULL,
  `rub_amount` DECIMAL(10,2) NOT NULL,
  `amount` INT UNSIGNED NOT NULL,
  `currency` CHAR(3) NOT NULL DEFAULT 'RUB',
  `status` ENUM('pending','awaiting_capture','succeeded','canceled','refunded','failed') NOT NULL DEFAULT 'pending',
  `ext_payment_id` VARCHAR(128) NULL,
  `confirmation_url` VARCHAR(512) NULL,
  `receipt_needed` TINYINT(1) NOT NULL DEFAULT 1,
  `receipt_email` VARCHAR(255) NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ux_payments_ext_id` (`ext_payment_id`),
  KEY `idx_payments_user_status` (`user_id`,`status`),
  CONSTRAINT `fk_payments_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `tasks` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id` BIGINT UNSIGNED NOT NULL,
  `task_uuid` VARCHAR(64) NOT NULL,
  `task_type` VARCHAR(20) NOT NULL,
  `model_name` VARCHAR(64) NOT NULL,
  `status` VARCHAR(32) NOT NULL DEFAULT 'queued',
  `credits_cost` INT UNSIGNED NOT NULL DEFAULT 0,
  `credits_used` INT UNSIGNED NOT NULL DEFAULT 0,
  `input_url` TEXT NULL,
  `result_url` TEXT NULL,
  `error_message` TEXT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `delivered` TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ux_tasks_uuid` (`task_uuid`),
  KEY `idx_tasks_user` (`user_id`),
  KEY `idx_tasks_delivered` (`delivered`),
  CONSTRAINT `fk_tasks_user` FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `broadcast_jobs` (
  `id` VARCHAR(36) NOT NULL,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_by` BIGINT NOT NULL,
  `text` TEXT NOT NULL,
  `status` VARCHAR(20) NOT NULL DEFAULT 'queued',
  `total` INT NOT NULL DEFAULT 0,
  `sent` INT NOT NULL DEFAULT 0,
  `failed` INT NOT NULL DEFAULT 0,
  `fallback` INT NOT NULL DEFAULT 0,
  `note` TEXT NULL,
  `media_type` VARCHAR(20) NULL,
  `media_file_id` TEXT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

COMMIT;
SET FOREIGN_KEY_CHECKS = 1;