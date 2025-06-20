-- MySQL迁移脚本
-- 创建数据库 (如果需要在MySQL客户端手动执行)
CREATE DATABASE IF NOT EXISTS campusnet_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 选择数据库
USE campusnet_db;

-- 创建账号表
CREATE TABLE IF NOT EXISTS accounts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    password VARCHAR(128) NOT NULL,
    is_bound BOOLEAN DEFAULT FALSE,
    student_id VARCHAR(32) NULL,
    bind_time DATETIME NULL,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 创建绑定日志表
CREATE TABLE IF NOT EXISTS binding_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(64) NOT NULL,
    student_id VARCHAR(32) NULL,
    bind_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    operator VARCHAR(64) DEFAULT 'system',
    action VARCHAR(32) NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 添加索引以提高查询性能
CREATE INDEX idx_username ON accounts(username);
CREATE INDEX idx_is_bound ON accounts(is_bound);
CREATE INDEX idx_student_id ON accounts(student_id);
CREATE INDEX idx_bind_time ON accounts(bind_time);

CREATE INDEX idx_log_username ON binding_logs(username);
CREATE INDEX idx_log_student_id ON binding_logs(student_id);
CREATE INDEX idx_log_bind_time ON binding_logs(bind_time);
CREATE INDEX idx_log_action ON binding_logs(action);
