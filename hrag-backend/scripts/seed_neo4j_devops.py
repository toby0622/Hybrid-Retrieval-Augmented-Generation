"""
Neo4j DevOps Seed Script
Creates sample DevOps infrastructure data for testing and demonstration.

Usage:
    python scripts/seed_neo4j_devops.py          # Seed data
    python scripts/seed_neo4j_devops.py --verify # Verify data
    python scripts/seed_neo4j_devops.py --clear  # Clear all data
"""

import argparse
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from neo4j import AsyncGraphDatabase
from config import settings


# Sample Services (8 microservices)
SERVICES = [
    {
        "name": "api-gateway",
        "version": "3.2.1",
        "language": "Go",
        "owner": "platform-team",
        "tier": "tier1-critical",
        "health_status": "healthy",
    },
    {
        "name": "auth-service",
        "version": "2.1.0",
        "language": "Python",
        "owner": "security-team",
        "tier": "tier1-critical",
        "health_status": "healthy",
    },
    {
        "name": "user-service",
        "version": "1.8.3",
        "language": "Java",
        "owner": "core-team",
        "tier": "tier2-important",
        "health_status": "healthy",
    },
    {
        "name": "payment-api",
        "version": "4.0.2",
        "language": "Go",
        "owner": "payments-team",
        "tier": "tier1-critical",
        "health_status": "degraded",
    },
    {
        "name": "notification-service",
        "version": "1.3.0",
        "language": "Node.js",
        "owner": "engagement-team",
        "tier": "tier3-normal",
        "health_status": "healthy",
    },
    {
        "name": "db-primary",
        "version": "PostgreSQL 15.2",
        "language": "SQL",
        "owner": "data-team",
        "tier": "tier1-critical",
        "health_status": "healthy",
    },
    {
        "name": "redis-cache",
        "version": "7.2.0",
        "language": "C",
        "owner": "platform-team",
        "tier": "tier2-important",
        "health_status": "healthy",
    },
    {
        "name": "message-queue",
        "version": "RabbitMQ 3.12",
        "language": "Erlang",
        "owner": "platform-team",
        "tier": "tier2-important",
        "health_status": "healthy",
    },
]

# Service Dependencies
DEPENDENCIES = [
    ("api-gateway", "auth-service", "gRPC", 50),
    ("api-gateway", "user-service", "REST", 100),
    ("api-gateway", "payment-api", "REST", 200),
    ("auth-service", "db-primary", "TCP", 20),
    ("auth-service", "redis-cache", "TCP", 5),
    ("user-service", "db-primary", "TCP", 30),
    ("payment-api", "db-primary", "TCP", 50),
    ("payment-api", "message-queue", "AMQP", 100),
    ("notification-service", "message-queue", "AMQP", 50),
]

# Sample Incidents (5 incidents)
INCIDENTS = [
    {
        "id": "INC-2024-001",
        "title": "Payment API 500 errors spike",
        "description": "Payment API返回大量500錯誤，導致訂單提交失敗。根因是資料庫連線池耗盡。",
        "severity": "SEV1",
        "status": "Resolved",
        "created_at": (datetime.now() - timedelta(days=3)).isoformat(),
        "resolved_at": (datetime.now() - timedelta(days=3, hours=-2)).isoformat(),
        "root_cause": "Database connection pool exhaustion due to leaked connections",
        "impact": "約30%的支付請求失敗，影響時間2小時",
        "affected_service": "payment-api",
    },
    {
        "id": "INC-2024-002",
        "title": "Auth service latency degradation",
        "description": "認證服務響應時間從50ms增加到500ms，影響所有需要認證的API。",
        "severity": "SEV2",
        "status": "Resolved",
        "created_at": (datetime.now() - timedelta(days=5)).isoformat(),
        "resolved_at": (datetime.now() - timedelta(days=5, hours=-1)).isoformat(),
        "root_cause": "Redis cache miss rate increased after TTL misconfiguration",
        "impact": "用戶登入延遲增加，約10%用戶受影響",
        "affected_service": "auth-service",
    },
    {
        "id": "INC-2024-003",
        "title": "Cache stampede on redis-cache",
        "description": "快取大量同時過期導致快取穿透，資料庫負載驟增。",
        "severity": "SEV2",
        "status": "Resolved",
        "created_at": (datetime.now() - timedelta(days=7)).isoformat(),
        "resolved_at": (datetime.now() - timedelta(days=7, hours=-3)).isoformat(),
        "root_cause": "All cache entries set with same TTL causing synchronized expiration",
        "impact": "系統整體延遲增加3倍，持續3小時",
        "affected_service": "redis-cache",
    },
    {
        "id": "INC-2024-004",
        "title": "Notification service OOM crash",
        "description": "通知服務因記憶體洩漏導致OOM被kill，部分通知延遲發送。",
        "severity": "SEV3",
        "status": "Investigating",
        "created_at": (datetime.now() - timedelta(hours=6)).isoformat(),
        "resolved_at": None,
        "root_cause": "Memory leak in email template rendering library",
        "impact": "約5%的通知延遲發送30分鐘",
        "affected_service": "notification-service",
    },
    {
        "id": "INC-2024-005",
        "title": "API Gateway connection refused errors",
        "description": "API Gateway間歇性出現connection refused錯誤，部分請求失敗。",
        "severity": "SEV1",
        "status": "Open",
        "created_at": (datetime.now() - timedelta(hours=1)).isoformat(),
        "resolved_at": None,
        "root_cause": None,
        "impact": "約15%的API請求失敗",
        "affected_service": "api-gateway",
    },
]

# Sample Metrics (10 metrics)
METRICS = [
    {"name": "cpu_usage", "value": 85.5, "unit": "percent", "service": "payment-api", "threshold": 80, "anomaly_score": 0.7},
    {"name": "memory_percent", "value": 92.3, "unit": "percent", "service": "notification-service", "threshold": 85, "anomaly_score": 0.9},
    {"name": "request_latency_p99", "value": 450, "unit": "ms", "service": "auth-service", "threshold": 200, "anomaly_score": 0.8},
    {"name": "error_rate", "value": 5.2, "unit": "percent", "service": "payment-api", "threshold": 1, "anomaly_score": 0.95},
    {"name": "db_connections", "value": 95, "unit": "count", "service": "db-primary", "threshold": 100, "anomaly_score": 0.85},
    {"name": "cache_hit_rate", "value": 45.0, "unit": "percent", "service": "redis-cache", "threshold": 80, "anomaly_score": 0.6},
    {"name": "queue_depth", "value": 15000, "unit": "count", "service": "message-queue", "threshold": 10000, "anomaly_score": 0.7},
    {"name": "request_throughput", "value": 1200, "unit": "rps", "service": "api-gateway", "threshold": None, "anomaly_score": 0.1},
    {"name": "gc_pause_time", "value": 120, "unit": "ms", "service": "user-service", "threshold": 100, "anomaly_score": 0.5},
    {"name": "disk_usage", "value": 78, "unit": "percent", "service": "db-primary", "threshold": 85, "anomaly_score": 0.2},
]

# Sample Logs (15 log entries)
LOGS = [
    {"level": "ERROR", "message": "Connection refused to db-primary:5432", "service": "payment-api", "trace_id": "abc123-def456"},
    {"level": "ERROR", "message": "NullPointerException in PaymentProcessor.process()", "service": "payment-api", "trace_id": "abc123-def456"},
    {"level": "WARN", "message": "Connection pool near capacity: 95/100", "service": "db-primary", "trace_id": None},
    {"level": "ERROR", "message": "Failed to acquire database connection within 5000ms", "service": "payment-api", "trace_id": "ghi789-jkl012"},
    {"level": "WARN", "message": "Cache miss rate exceeded threshold: 55%", "service": "redis-cache", "trace_id": None},
    {"level": "INFO", "message": "Service started successfully on port 8080", "service": "auth-service", "trace_id": None},
    {"level": "ERROR", "message": "OutOfMemoryError: Java heap space", "service": "notification-service", "trace_id": "mno345-pqr678"},
    {"level": "WARN", "message": "Request latency exceeded SLO: 450ms > 200ms", "service": "auth-service", "trace_id": "stu901-vwx234"},
    {"level": "ERROR", "message": "Circuit breaker opened for payment-api", "service": "api-gateway", "trace_id": "yza567-bcd890"},
    {"level": "INFO", "message": "Deployment completed: v4.0.2", "service": "payment-api", "trace_id": None},
    {"level": "ERROR", "message": "SSL handshake timeout with upstream", "service": "api-gateway", "trace_id": "efg123-hij456"},
    {"level": "WARN", "message": "Retry attempt 3/5 for message delivery", "service": "notification-service", "trace_id": "klm789-nop012"},
    {"level": "ERROR", "message": "Authentication token validation failed: expired", "service": "auth-service", "trace_id": "qrs345-tuv678"},
    {"level": "INFO", "message": "Health check passed", "service": "user-service", "trace_id": None},
    {"level": "FATAL", "message": "Process killed by OOM killer", "service": "notification-service", "trace_id": None},
]


async def clear_data(driver):
    """Clear all existing data."""
    print("🗑️  Clearing existing data...")
    async with driver.session() as session:
        await session.run("MATCH (n) DETACH DELETE n")
    print("   Done.")


async def seed_services(driver):
    """Create Service nodes."""
    print("📦 Creating Service nodes...")
    async with driver.session() as session:
        for svc in SERVICES:
            await session.run(
                """
                CREATE (s:Service {
                    name: $name,
                    version: $version,
                    language: $language,
                    owner: $owner,
                    tier: $tier,
                    health_status: $health_status,
                    last_deploy: datetime()
                })
                """,
                **svc
            )
    print(f"   Created {len(SERVICES)} services.")


async def seed_dependencies(driver):
    """Create DEPENDS_ON relationships."""
    print("🔗 Creating service dependencies...")
    async with driver.session() as session:
        for src, tgt, protocol, latency in DEPENDENCIES:
            await session.run(
                """
                MATCH (a:Service {name: $src}), (b:Service {name: $tgt})
                CREATE (a)-[:DEPENDS_ON {protocol: $protocol, latency_budget_ms: $latency}]->(b)
                """,
                src=src, tgt=tgt, protocol=protocol, latency=latency
            )
    print(f"   Created {len(DEPENDENCIES)} dependencies.")


async def seed_incidents(driver):
    """Create Incident nodes and AFFECTS relationships."""
    print("🚨 Creating Incident nodes...")
    async with driver.session() as session:
        for inc in INCIDENTS:
            await session.run(
                """
                CREATE (i:Incident {
                    id: $id,
                    title: $title,
                    description: $description,
                    severity: $severity,
                    status: $status,
                    created_at: $created_at,
                    resolved_at: $resolved_at,
                    root_cause: $root_cause,
                    impact: $impact
                })
                WITH i
                MATCH (s:Service {name: $affected_service})
                CREATE (i)-[:AFFECTS]->(s)
                """,
                **inc
            )
    print(f"   Created {len(INCIDENTS)} incidents with AFFECTS relations.")


async def seed_metrics(driver):
    """Create Metric nodes and MEASURES relationships."""
    print("📊 Creating Metric nodes...")
    async with driver.session() as session:
        for metric in METRICS:
            await session.run(
                """
                CREATE (m:Metric {
                    name: $name,
                    value: $value,
                    unit: $unit,
                    threshold: $threshold,
                    anomaly_score: $anomaly_score,
                    timestamp: datetime()
                })
                WITH m
                MATCH (s:Service {name: $service})
                CREATE (m)-[:MEASURES]->(s)
                """,
                **metric
            )
    print(f"   Created {len(METRICS)} metrics with MEASURES relations.")


async def seed_logs(driver):
    """Create Log nodes and GENERATED_BY relationships."""
    print("📝 Creating Log nodes...")
    async with driver.session() as session:
        for i, log in enumerate(LOGS):
            await session.run(
                """
                CREATE (l:Log {
                    level: $level,
                    message: $message,
                    trace_id: $trace_id,
                    timestamp: datetime() - duration({minutes: $offset})
                })
                WITH l
                MATCH (s:Service {name: $service})
                CREATE (l)-[:GENERATED_BY]->(s)
                """,
                **log,
                offset=len(LOGS) - i  # Stagger timestamps
            )
    print(f"   Created {len(LOGS)} log entries with GENERATED_BY relations.")


async def seed_triggered_by(driver):
    """Create TRIGGERED_BY relationships between incidents and anomalous metrics."""
    print("⚡ Creating TRIGGERED_BY relationships...")
    async with driver.session() as session:
        # INC-001 triggered by error_rate metric
        await session.run(
            """
            MATCH (i:Incident {id: 'INC-2024-001'}), (m:Metric {name: 'error_rate'})
            CREATE (i)-[:TRIGGERED_BY]->(m)
            """
        )
        # INC-002 triggered by latency metric
        await session.run(
            """
            MATCH (i:Incident {id: 'INC-2024-002'}), (m:Metric {name: 'request_latency_p99'})
            CREATE (i)-[:TRIGGERED_BY]->(m)
            """
        )
        # INC-003 triggered by cache hit rate
        await session.run(
            """
            MATCH (i:Incident {id: 'INC-2024-003'}), (m:Metric {name: 'cache_hit_rate'})
            CREATE (i)-[:TRIGGERED_BY]->(m)
            """
        )
        # INC-004 triggered by memory metric
        await session.run(
            """
            MATCH (i:Incident {id: 'INC-2024-004'}), (m:Metric {name: 'memory_percent'})
            CREATE (i)-[:TRIGGERED_BY]->(m)
            """
        )
    print("   Created TRIGGERED_BY relationships.")


async def verify_data(driver):
    """Verify seeded data."""
    print("\n🔍 Verifying data...\n")
    async with driver.session() as session:
        # Count nodes by label
        result = await session.run(
            """
            CALL {
                MATCH (s:Service) RETURN 'Service' as label, count(s) as count
                UNION ALL
                MATCH (i:Incident) RETURN 'Incident' as label, count(i) as count
                UNION ALL
                MATCH (m:Metric) RETURN 'Metric' as label, count(m) as count
                UNION ALL
                MATCH (l:Log) RETURN 'Log' as label, count(l) as count
            }
            RETURN label, count
            """
        )
        records = await result.data()
        
        print("   Node Counts:")
        total_nodes = 0
        for rec in records:
            print(f"     {rec['label']}: {rec['count']}")
            total_nodes += rec['count']
        print(f"     Total: {total_nodes}")
        
        # Count relationships
        result = await session.run(
            """
            CALL {
                MATCH ()-[r:DEPENDS_ON]->() RETURN 'DEPENDS_ON' as type, count(r) as count
                UNION ALL
                MATCH ()-[r:AFFECTS]->() RETURN 'AFFECTS' as type, count(r) as count
                UNION ALL
                MATCH ()-[r:MEASURES]->() RETURN 'MEASURES' as type, count(r) as count
                UNION ALL
                MATCH ()-[r:GENERATED_BY]->() RETURN 'GENERATED_BY' as type, count(r) as count
                UNION ALL
                MATCH ()-[r:TRIGGERED_BY]->() RETURN 'TRIGGERED_BY' as type, count(r) as count
            }
            RETURN type, count
            """
        )
        records = await result.data()
        
        print("\n   Relationship Counts:")
        total_rels = 0
        for rec in records:
            print(f"     {rec['type']}: {rec['count']}")
            total_rels += rec['count']
        print(f"     Total: {total_rels}")
        
        # Sample query
        print("\n   Sample Query - Services with incidents:")
        result = await session.run(
            """
            MATCH (i:Incident)-[:AFFECTS]->(s:Service)
            RETURN s.name as service, i.severity as severity, i.title as incident
            ORDER BY i.severity
            LIMIT 5
            """
        )
        records = await result.data()
        for rec in records:
            print(f"     [{rec['severity']}] {rec['service']}: {rec['incident']}")
    
    print("\n✅ Verification complete!")


async def main():
    parser = argparse.ArgumentParser(description="Neo4j DevOps Seed Script")
    parser.add_argument("--verify", action="store_true", help="Verify data only")
    parser.add_argument("--clear", action="store_true", help="Clear all data")
    args = parser.parse_args()

    print(f"🔌 Connecting to Neo4j at {settings.neo4j_uri}...")
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password)
    )

    try:
        # Test connection
        async with driver.session() as session:
            await session.run("RETURN 1")
        print("   Connected successfully!\n")

        if args.clear:
            await clear_data(driver)
        elif args.verify:
            await verify_data(driver)
        else:
            # Full seed
            await clear_data(driver)
            await seed_services(driver)
            await seed_dependencies(driver)
            await seed_incidents(driver)
            await seed_metrics(driver)
            await seed_logs(driver)
            await seed_triggered_by(driver)
            await verify_data(driver)
            
            print("\n🎉 Seeding complete!")

    finally:
        await driver.close()


if __name__ == "__main__":
    asyncio.run(main())
