"""
Database Initialization Script
Populates Neo4j and Qdrant with sample data for HRAG demo
"""

import os
import asyncio
from neo4j import AsyncGraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import numpy as np

# Load from .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Configuration from environment variables (with defaults for local dev)
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "hrag_documents")

# LM Studio embedding configuration
LM_STUDIO_URL = os.getenv("LLM_BASE_URL", "http://localhost:8192/v1")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-embeddinggemma-300m")

# Embedding dimension for embeddinggemma-300m (768 dimensions)
EMBEDDING_DIM = 768


async def init_neo4j():
    """Initialize Neo4j with sample DevOps topology data"""
    print("🔵 Connecting to Neo4j...")
    
    driver = AsyncGraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USER, NEO4J_PASSWORD)
    )
    
    async with driver.session() as session:
        # Clear existing data
        print("   Clearing existing data...")
        await session.run("MATCH (n) DETACH DELETE n")
        
        # Create Services
        print("   Creating service nodes...")
        services = [
            ("PaymentService", "v2.4.1-hotfix", "2025-01-29T09:15:00Z"),
            ("OrderService", "v3.1.0", "2025-01-28T14:30:00Z"),
            ("UserService", "v2.0.5", "2025-01-27T10:00:00Z"),
            ("NotificationService", "v1.8.2", "2025-01-25T08:00:00Z"),
            ("InventoryService", "v2.2.0", "2025-01-26T16:45:00Z"),
        ]
        
        for name, version, deployed_at in services:
            await session.run("""
                CREATE (s:Service {
                    name: $name, 
                    version: $version, 
                    deployed_at: $deployed_at,
                    status: 'running'
                })
            """, name=name, version=version, deployed_at=deployed_at)
        
        # Create Infrastructure
        print("   Creating infrastructure nodes...")
        infra = [
            ("PostgreSQL-Primary", "Database", "db-prod-1"),
            ("PostgreSQL-Replica", "Database", "db-prod-2"),
            ("Redis-Cache", "Cache", "cache-prod-1"),
            ("Redis-Session", "Cache", "cache-prod-2"),
            ("Kafka-Cluster", "MessageQueue", "mq-prod-1"),
            ("K8s-Cluster-Alpha", "Kubernetes", "k8s-prod-alpha"),
        ]
        
        for name, infra_type, host in infra:
            await session.run("""
                CREATE (i:Infrastructure {
                    name: $name,
                    type: $type,
                    host: $host,
                    status: 'healthy'
                })
            """, name=name, type=infra_type, host=host)
        
        # Create Configurations
        print("   Creating configuration nodes...")
        configs = [
            ("HikariCP-Config", "PaymentService", {"max_pool_size": 10, "min_idle": 5, "timeout_ms": 3000}),
            ("Redis-Config", "PaymentService", {"ttl_seconds": 300, "max_connections": 50}),
            ("Kafka-Producer-Config", "OrderService", {"batch_size": 16384, "linger_ms": 5}),
        ]
        
        for name, service, props in configs:
            await session.run("""
                CREATE (c:Config {
                    name: $name,
                    service: $service,
                    max_pool_size: $max_pool_size,
                    timeout_ms: $timeout_ms
                })
            """, name=name, service=service, 
                max_pool_size=props.get("max_pool_size", 0),
                timeout_ms=props.get("timeout_ms", 0))
        
        # Create Events/Incidents
        print("   Creating event nodes...")
        events = [
            ("INC-2025-001", "Connection Pool Exhausted", "2025-01-29T09:30:00Z", "critical"),
            ("INC-2025-002", "High Latency Alert", "2025-01-28T14:45:00Z", "warning"),
            ("DEPLOY-2025-015", "PaymentService Hotfix Deployment", "2025-01-29T09:15:00Z", "info"),
        ]
        
        for event_id, description, timestamp, severity in events:
            await session.run("""
                CREATE (e:Event {
                    event_id: $event_id,
                    description: $description,
                    timestamp: $timestamp,
                    severity: $severity
                })
            """, event_id=event_id, description=description, timestamp=timestamp, severity=severity)
        
        # Create Relationships
        print("   Creating relationships...")
        
        # Service dependencies
        await session.run("""
            MATCH (s:Service {name: 'PaymentService'}), (db:Infrastructure {name: 'PostgreSQL-Primary'})
            CREATE (s)-[:DEPENDS_ON {connection_type: 'jdbc', pool_size: 10}]->(db)
        """)
        await session.run("""
            MATCH (s:Service {name: 'PaymentService'}), (cache:Infrastructure {name: 'Redis-Cache'})
            CREATE (s)-[:DEPENDS_ON {connection_type: 'redis', purpose: 'session'}]->(cache)
        """)
        await session.run("""
            MATCH (s:Service {name: 'OrderService'}), (kafka:Infrastructure {name: 'Kafka-Cluster'})
            CREATE (s)-[:PUBLISHES_TO {topic: 'order-events'}]->(kafka)
        """)
        await session.run("""
            MATCH (s:Service {name: 'PaymentService'}), (kafka:Infrastructure {name: 'Kafka-Cluster'})
            CREATE (s)-[:SUBSCRIBES_TO {topic: 'order-events'}]->(kafka)
        """)
        
        # Service to K8s
        await session.run("""
            MATCH (s:Service), (k8s:Infrastructure {name: 'K8s-Cluster-Alpha'})
            CREATE (s)-[:DEPLOYED_ON {namespace: 'production'}]->(k8s)
        """)
        
        # Config to Service
        await session.run("""
            MATCH (c:Config {name: 'HikariCP-Config'}), (s:Service {name: 'PaymentService'})
            CREATE (c)-[:CONFIGURES]->(s)
        """)
        
        # Event to Service
        await session.run("""
            MATCH (e:Event {event_id: 'INC-2025-001'}), (s:Service {name: 'PaymentService'})
            CREATE (e)-[:AFFECTS]->(s)
        """)
        await session.run("""
            MATCH (e:Event {event_id: 'DEPLOY-2025-015'}), (s:Service {name: 'PaymentService'})
            CREATE (e)-[:TRIGGERED_BY]->(s)
        """)
        
        # Causation
        await session.run("""
            MATCH (deploy:Event {event_id: 'DEPLOY-2025-015'}), (inc:Event {event_id: 'INC-2025-001'})
            CREATE (deploy)-[:CAUSED {confidence: 0.92}]->(inc)
        """)
        
        print("   ✅ Neo4j initialized successfully!")
        
        # Verify
        result = await session.run("MATCH (n) RETURN labels(n) as labels, count(*) as count")
        records = await result.data()
        for record in records:
            print(f"      - {record['labels']}: {record['count']} nodes")
    
    await driver.close()


def get_embedding(text: str, use_lm_studio: bool = True) -> list:
    """Get embedding from LM Studio or fallback to random."""
    if use_lm_studio:
        try:
            import httpx
            response = httpx.post(
                f"{LM_STUDIO_URL}/embeddings",
                json={"model": EMBEDDING_MODEL, "input": text},
                headers={"Authorization": "Bearer lm-studio"},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()["data"][0]["embedding"]
        except Exception as e:
            print(f"      LM Studio embedding failed: {e}, using fallback")
    
    # Fallback to deterministic random embedding
    content_hash = hash(text) % 10000
    np.random.seed(content_hash)
    embedding = np.random.randn(EMBEDDING_DIM).astype(np.float32)
    return (embedding / np.linalg.norm(embedding)).tolist()


def init_qdrant(use_lm_studio: bool = True):
    """Initialize Qdrant with sample document embeddings"""
    print("\n🟢 Connecting to Qdrant...")
    
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    
    # Delete collection if exists
    try:
        client.delete_collection(QDRANT_COLLECTION)
        print("   Deleted existing collection")
    except:
        pass
    
    # Create collection
    print(f"   Creating collection '{QDRANT_COLLECTION}'...")
    client.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE)
    )
    
    # Sample documents
    documents = [
        {
            "id": 1,
            "title": "Post-Mortem #402: HikariCP Pool Exhaustion",
            "content": "Root Cause: Connection pool size was reset to default (10) after deployment. Under load, this caused connection exhaustion and timeout errors. The v2.4.1-hotfix deployment accidentally overwrote the HikariCP configuration, resetting maximum-pool-size from 50 to 10.",
            "document_type": "post_mortem",
            "service": "PaymentService",
            "date": "2025-01-15",
            "tags": ["hikaricp", "connection-pool", "timeout", "deployment"]
        },
        {
            "id": 2,
            "title": "SOP: Database Connection Troubleshooting",
            "content": "Steps for diagnosing connection issues: 1. Check HikariCP metrics in Grafana 2. Verify pool size configuration in ConfigMap 3. Review recent deployments 4. Check database server load 5. Examine connection timeout settings.",
            "document_type": "sop",
            "service": "PaymentService",
            "category": "database",
            "tags": ["database", "troubleshooting", "hikaricp", "connection"]
        },
        {
            "id": 3,
            "title": "Post-Mortem #389: Redis Session Timeout",
            "content": "During peak traffic, Redis session store experienced timeouts due to insufficient max connections. Resolution: Increased max connections from 50 to 200 and implemented connection pooling.",
            "document_type": "post_mortem",
            "service": "UserService",
            "date": "2025-01-10",
            "tags": ["redis", "session", "timeout", "connection"]
        },
        {
            "id": 4,
            "title": "SOP: Kubernetes Deployment Rollback",
            "content": "To rollback a deployment: 1. kubectl rollout undo deployment/<name> 2. Verify pods are healthy 3. Check service endpoints 4. Monitor error rates in Grafana 5. Update incident ticket.",
            "document_type": "sop",
            "category": "kubernetes",
            "tags": ["kubernetes", "rollback", "deployment"]
        },
        {
            "id": 5,
            "title": "Post-Mortem #401: Kafka Consumer Lag",
            "content": "OrderService consumers fell behind due to slow database writes. Root cause was missing index on orders table. Added composite index on (user_id, created_at) which reduced query time from 500ms to 5ms.",
            "document_type": "post_mortem",
            "service": "OrderService",
            "date": "2025-01-20",
            "tags": ["kafka", "consumer-lag", "database", "index"]
        },
        {
            "id": 6,
            "title": "Architecture: PaymentService Dependencies",
            "content": "PaymentService depends on: PostgreSQL-Primary for transaction data, Redis-Cache for session management, Kafka for event streaming. Critical path: API -> Redis (auth) -> PostgreSQL (transaction) -> Kafka (event publish).",
            "document_type": "architecture",
            "service": "PaymentService",
            "tags": ["architecture", "dependencies", "critical-path"]
        },
        {
            "id": 7,
            "title": "Runbook: High Latency Investigation",
            "content": "When investigating high latency: 1. Check Jaeger traces for slow spans 2. Verify database connection pool metrics 3. Check downstream service health 4. Review recent config changes 5. Check resource utilization (CPU, memory, disk I/O).",
            "document_type": "runbook",
            "category": "performance",
            "tags": ["latency", "performance", "investigation", "tracing"]
        },
        {
            "id": 8,
            "title": "Config Reference: HikariCP Best Practices",
            "content": "Recommended HikariCP settings for production: maximum-pool-size=50, minimum-idle=10, idle-timeout=300000, max-lifetime=1800000, connection-timeout=30000. Always set these explicitly to prevent reset on deployment.",
            "document_type": "reference",
            "category": "configuration",
            "tags": ["hikaricp", "configuration", "best-practices", "connection-pool"]
        },
    ]
    
    # Generate embeddings
    mode = "LM Studio" if use_lm_studio else "random fallback"
    print(f"   Generating embeddings ({mode})...")
    
    points = []
    for i, doc in enumerate(documents):
        print(f"      [{i+1}/{len(documents)}] {doc['title'][:40]}...")
        embedding = get_embedding(doc["content"], use_lm_studio)
        
        points.append(PointStruct(
            id=doc["id"],
            vector=embedding,
            payload={
                "title": doc["title"],
                "content": doc["content"],
                "document_type": doc.get("document_type", ""),
                "service": doc.get("service", ""),
                "category": doc.get("category", ""),
                "date": doc.get("date", ""),
                "tags": doc.get("tags", [])
            }
        ))
    
    client.upsert(collection_name=QDRANT_COLLECTION, points=points)
    
    print(f"   ✅ Qdrant initialized with {len(documents)} documents!")
    
    # Verify
    collection_info = client.get_collection(QDRANT_COLLECTION)
    print(f"      - Collection: {QDRANT_COLLECTION}")
    print(f"      - Points: {collection_info.points_count}")


async def main():
    print("=" * 60)
    print("HRAG Database Initialization")
    print("=" * 60)
    
    try:
        await init_neo4j()
    except Exception as e:
        print(f"   ❌ Neo4j initialization failed: {e}")
    
    try:
        init_qdrant()
    except Exception as e:
        print(f"   ❌ Qdrant initialization failed: {e}")
    
    print("\n" + "=" * 60)
    print("Initialization complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
