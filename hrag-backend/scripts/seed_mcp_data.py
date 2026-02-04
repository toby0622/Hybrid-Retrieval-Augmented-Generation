"""
Seed script for MCP PostgreSQL database.

Creates the required tables and inserts sample data for demo purposes.
Run this script to set up the MCP database:

    python scripts/seed_mcp_data.py

Prerequisites:
    1. PostgreSQL server running
    2. Database 'hrag_mcp' created (or use different name via env)
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg
from config import settings

CREATE_TABLES_SQL = """
-- Service Metrics Table
CREATE TABLE IF NOT EXISTS service_metrics (
    id SERIAL PRIMARY KEY,
    service_name VARCHAR(100) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_value NUMERIC NOT NULL,
    unit VARCHAR(20),
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- Service Logs Table
CREATE TABLE IF NOT EXISTS service_logs (
    id SERIAL PRIMARY KEY,
    service_name VARCHAR(100) NOT NULL,
    log_level VARCHAR(20) NOT NULL,
    message TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- Service Health Table
CREATE TABLE IF NOT EXISTS service_health (
    id SERIAL PRIMARY KEY,
    service_name VARCHAR(100) NOT NULL,
    health_status VARCHAR(20) NOT NULL,
    last_check TIMESTAMPTZ DEFAULT NOW(),
    details TEXT
);

-- Generic Real-time Data Table
CREATE TABLE IF NOT EXISTS realtime_data (
    id SERIAL PRIMARY KEY,
    data_type VARCHAR(100) NOT NULL,
    data_key VARCHAR(100) NOT NULL,
    data_value TEXT,
    metadata JSONB,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_metrics_service ON service_metrics(service_name);
CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON service_metrics(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_logs_service ON service_logs(service_name);
CREATE INDEX IF NOT EXISTS idx_logs_level ON service_logs(log_level);
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON service_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_health_service ON service_health(service_name);
CREATE INDEX IF NOT EXISTS idx_realtime_type ON realtime_data(data_type);
"""


SAMPLE_SERVICES = [
    "auth-service",
    "api-gateway",
    "user-service",
    "payment-service",
    "notification-service",
    "cache-service",
    "database-proxy",
]

SAMPLE_METRICS = [
    ("cpu_usage", "%"),
    ("memory_usage", "%"),
    ("request_latency", "ms"),
    ("error_rate", "%"),
    ("active_connections", "count"),
    ("throughput", "req/s"),
]

LOG_LEVELS = ["DEBUG", "INFO", "WARN", "ERROR"]

SAMPLE_LOG_MESSAGES = {
    "DEBUG": [
        "Processing request from client",
        "Cache lookup initiated",
        "Connection pool status checked",
    ],
    "INFO": [
        "Service started successfully",
        "Health check passed",
        "Configuration reloaded",
        "New connection established",
    ],
    "WARN": [
        "High memory usage detected",
        "Connection pool nearing capacity",
        "Retry attempt for external service",
        "Response time exceeded threshold",
    ],
    "ERROR": [
        "Failed to connect to database",
        "Request timeout after 30s",
        "Authentication failed for user",
        "Out of memory exception",
        "Circuit breaker triggered",
    ],
}


async def seed_database():
    """Create tables and insert sample data."""
    print(
        f"[MCP Seed] Connecting to PostgreSQL at {settings.mcp_db_host}:{settings.mcp_db_port}"
    )
    print(f"[MCP Seed] Database: {settings.mcp_db_name}")

    try:
        conn = await asyncpg.connect(
            host=settings.mcp_db_host,
            port=settings.mcp_db_port,
            database=settings.mcp_db_name,
            user=settings.mcp_db_user,
            password=settings.mcp_db_password,
        )
    except Exception as e:
        print(f"[MCP Seed] Connection failed: {e}")
        print("[MCP Seed] Make sure PostgreSQL is running and database exists.")
        print(
            f"[MCP Seed] Create database with: CREATE DATABASE {settings.mcp_db_name};"
        )
        return False

    print("[MCP Seed] Connected successfully!")

    print("[MCP Seed] Creating tables...")
    await conn.execute(CREATE_TABLES_SQL)
    print("[MCP Seed] Tables created.")

    print("[MCP Seed] Clearing existing data...")
    await conn.execute(
        "TRUNCATE service_metrics, service_logs, service_health, realtime_data RESTART IDENTITY"
    )

    print("[MCP Seed] Inserting sample metrics...")
    import random

    now = datetime.now()

    for service in SAMPLE_SERVICES:
        for metric_name, unit in SAMPLE_METRICS:
            for i in range(10):
                timestamp = now - timedelta(minutes=i * 5)

                if metric_name == "cpu_usage":
                    value = random.uniform(15, 85)
                elif metric_name == "memory_usage":
                    value = random.uniform(30, 90)
                elif metric_name == "request_latency":
                    value = random.uniform(50, 500)
                elif metric_name == "error_rate":
                    value = random.uniform(0, 5)
                elif metric_name == "active_connections":
                    value = random.randint(10, 200)
                else:
                    value = random.uniform(100, 1000)

                await conn.execute(
                    """
                    INSERT INTO service_metrics (service_name, metric_name, metric_value, unit, timestamp)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    service,
                    metric_name,
                    round(value, 2),
                    unit,
                    timestamp,
                )

    print("[MCP Seed] Inserting sample logs...")
    for service in SAMPLE_SERVICES:
        for i in range(20):
            timestamp = now - timedelta(minutes=i * 3)
            log_level = random.choice(LOG_LEVELS)

            if service in ["payment-service", "auth-service"] and i < 5:
                log_level = "ERROR"

            messages = SAMPLE_LOG_MESSAGES[log_level]
            message = random.choice(messages)

            await conn.execute(
                """
                INSERT INTO service_logs (service_name, log_level, message, timestamp)
                VALUES ($1, $2, $3, $4)
                """,
                service,
                log_level,
                message,
                timestamp,
            )

    print("[MCP Seed] Inserting service health status...")
    health_states = ["healthy", "healthy", "healthy", "degraded", "unhealthy"]
    for service in SAMPLE_SERVICES:
        status = random.choice(health_states)

        if service == "payment-service":
            status = "degraded"
            details = "High latency detected, investigating root cause"
        elif service == "auth-service":
            status = "unhealthy"
            details = "Connection to identity provider failed"
        else:
            details = (
                "All checks passed" if status == "healthy" else "Minor issues detected"
            )

        await conn.execute(
            """
            INSERT INTO service_health (service_name, health_status, last_check, details)
            VALUES ($1, $2, $3, $4)
            """,
            service,
            status,
            now,
            details,
        )

    print("[MCP Seed] Inserting sample real-time data...")
    realtime_entries = [
        ("cluster_info", "active_nodes", "5", {"region": "us-west-2"}),
        ("cluster_info", "pending_pods", "3", {"namespace": "production"}),
        ("deployment", "latest_version", "v2.3.1", {"service": "api-gateway"}),
        ("alert", "active_alerts", "2", {"severity": "warning"}),
    ]

    for data_type, data_key, data_value, metadata in realtime_entries:
        import json

        await conn.execute(
            """
            INSERT INTO realtime_data (data_type, data_key, data_value, metadata, timestamp)
            VALUES ($1, $2, $3, $4, $5)
            """,
            data_type,
            data_key,
            data_value,
            json.dumps(metadata),
            now,
        )

    await conn.close()

    print("[MCP Seed] ✅ Database seeded successfully!")
    print(f"[MCP Seed] Inserted data for {len(SAMPLE_SERVICES)} services")
    return True


if __name__ == "__main__":
    success = asyncio.run(seed_database())
    sys.exit(0 if success else 1)
