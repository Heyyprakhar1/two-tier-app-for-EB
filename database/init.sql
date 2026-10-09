-- Database initialization for DevOps Deployment Dashboard
-- Runs automatically on initial startup of the MySQL container

CREATE DATABASE IF NOT EXISTS devops_dashboard;
USE devops_dashboard;

CREATE TABLE IF NOT EXISTS deployments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    application VARCHAR(100) NOT NULL,
    version VARCHAR(50) NOT NULL,
    environment VARCHAR(50) NOT NULL,
    status ENUM('SUCCESS', 'FAILED', 'IN_PROGRESS') NOT NULL DEFAULT 'IN_PROGRESS',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Seed initial demonstration records
INSERT INTO deployments (application, version, environment, status) VALUES
('frontend', 'v1.4.0', 'production', 'SUCCESS'),
('backend', 'v2.1.0', 'staging', 'SUCCESS'),
('api-gateway', 'v1.9.2', 'production', 'FAILED'),
('worker', 'v1.3.1', 'development', 'IN_PROGRESS');