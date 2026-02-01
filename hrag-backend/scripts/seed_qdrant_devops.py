import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from config import settings

EMBEDDING_DIM = 768


POSTMORTEMS = [
    {
        "title": "Postmortem: Payment API Database Connection Pool Exhaustion",
        "doc_type": "postmortem",
        "service": "payment-api",
        "incident_id": "INC-2024-001",
        "severity": "SEV1",
        "content": """## Incident Summary
On 2024-01-28, the payment-api service experienced a severe outage lasting approximately 2 hours. 
During this time, approximately 30% of payment requests failed with 500 errors.

## Timeline
- 14:00 - First alerts triggered for elevated error rates
- 14:05 - On-call engineer paged
- 14:15 - Root cause identified: database connection pool exhausted
- 14:30 - Mitigation: Increased connection pool size temporarily
- 16:00 - Permanent fix deployed: Fixed connection leak in payment processor

## Root Cause
A bug introduced in v4.0.0 caused database connections to not be properly returned to the pool 
when certain error conditions occurred in the PaymentProcessor class. Over time, this led to 
connection pool exhaustion.

## Resolution
1. Hotfix deployed to properly close connections in error handlers
2. Added connection pool monitoring alerts
3. Implemented connection timeout settings

## Action Items
- [ ] Add integration tests for connection pool management
- [ ] Implement circuit breaker for database connections
- [x] Add Grafana dashboard for connection pool metrics
"""
    },
    {
        "title": "Postmortem: Auth Service Latency Degradation",
        "doc_type": "postmortem",
        "service": "auth-service",
        "incident_id": "INC-2024-002",
        "severity": "SEV2",
        "content": """## Incident Summary
The auth-service experienced significant latency degradation, with p99 latency increasing 
from 50ms to 500ms. This affected all services requiring authentication.

## Timeline
- 09:00 - Deployment of new cache TTL configuration
- 11:30 - Users report slow login times
- 12:00 - Investigation started
- 12:30 - Root cause identified: Cache TTL too short
- 13:00 - Configuration rollback completed

## Root Cause
A configuration change reduced Redis cache TTL from 1 hour to 1 minute, causing 
excessive cache misses and database queries. The change was intended to reduce 
stale data but was not properly tested under load.

## Resolution
1. Rolled back TTL configuration
2. Implemented gradual TTL reduction with monitoring
3. Added cache hit rate alerts

## Lessons Learned
- Configuration changes need load testing
- Cache hit rate should be a key SLI
"""
    },
    {
        "title": "Postmortem: Redis Cache Stampede",
        "doc_type": "postmortem",
        "service": "redis-cache",
        "incident_id": "INC-2024-003",
        "severity": "SEV2",
        "content": """## Incident Summary
A cache stampede occurred when a large number of cache entries expired simultaneously,
causing a surge of database queries that overloaded the primary database.

## Timeline
- 03:00 - Bulk cache population with identical TTL
- 04:00 - All entries expire simultaneously
- 04:01 - Database CPU spikes to 100%
- 04:15 - Auto-scaling triggered for database replicas
- 07:00 - Situation stabilized

## Root Cause
During a data migration, 50,000 cache entries were populated with identical TTL values,
causing synchronized expiration and a thundering herd problem.

## Resolution
1. Implemented jittered TTL (base TTL + random offset)
2. Added cache warming for critical data paths
3. Configured request coalescing for cache misses

## Prevention
- Cache population scripts now use randomized TTL
- Monitoring for cache expiration patterns
""",
    },
    {
        "title": "Postmortem: Notification Service OOM Crashes",
        "doc_type": "postmortem",
        "service": "notification-service",
        "incident_id": "INC-2024-004",
        "severity": "SEV3",
        "content": """## Incident Summary
The notification-service experienced repeated OOM (Out of Memory) crashes,
causing delays in email and push notification delivery.

## Timeline
- 10:00 - First OOM crash detected
- 10:05 - Pod automatically restarted by Kubernetes
- 10:30 - Second OOM crash
- 11:00 - Investigation started
- 14:00 - Memory leak identified in email template engine
- 14:00 - Root cause identified: unbounded template cache
- 14:00 - Fix deployed: LRU cache with 100 entry limit

## Root Cause
A memory leak in the email template rendering library (Handlebars.js) caused
memory usage to grow unbounded when processing templates with large data payloads.
The leak occurred because compiled templates were being cached without size limits.

## Resolution
1. Upgraded Handlebars.js to patched version
2. Implemented LRU cache for compiled templates
3. Added memory usage alerts and auto-restart thresholds

## Impact
- ~5% of notifications delayed by 30 minutes
- No data loss due to message queue persistence
""",
    },
    {
        "title": "Postmortem: API Gateway Connection Refused Errors",
        "doc_type": "postmortem",
        "service": "api-gateway",
        "incident_id": "INC-2024-005",
        "severity": "SEV1",
        "content": """## Incident Summary
The api-gateway experienced intermittent connection refused errors,
causing approximately 15% of API requests to fail.

## Timeline
- 16:00 - Initial alerts for elevated 5xx errors
- 16:05 - On-call paged
- 16:30 - Pattern identified: errors correlate with specific pods
- 17:00 - Investigation ongoing

## Current Investigation
- Kubernetes node resource exhaustion suspected
- Network policy changes recently deployed
- Possible ephemeral port exhaustion

## Preliminary Root Cause
Under investigation. Suspected to be related to:
1. Pod resource limits too restrictive
2. Network policy blocking internal traffic
3. Load balancer health check misconfiguration

## Interim Mitigations
- Increased pod replica count
- Disabled problematic network policy
- Enhanced monitoring for connection errors
""",
    },
]

RUNBOOKS = [
    {
        "title": "Runbook: Database Connection Pool Exhaustion",
        "doc_type": "runbook",
        "service": "db-primary",
        "content": """# Database Connection Pool Exhaustion Runbook

## Symptoms
- Services reporting "Connection pool exhausted" errors
- Database connections at or near limit
- Slow query execution times

## Diagnosis Steps
1. Check current connection count:
   ```sql
   SELECT count(*) FROM pg_stat_activity;
   ```
2. Identify connection sources:
   ```sql
   SELECT application_name, count(*) 
   FROM pg_stat_activity 
   GROUP BY application_name;
   ```
3. Check for long-running queries:
   ```sql
   SELECT pid, now() - query_start as duration, query 
   FROM pg_stat_activity 
   WHERE state = 'active' 
   ORDER BY duration DESC;
   ```

## Immediate Mitigation
1. Kill idle connections older than 10 minutes:
   ```sql
   SELECT pg_terminate_backend(pid) 
   FROM pg_stat_activity 
   WHERE state = 'idle' 
   AND query_start < now() - interval '10 minutes';
   ```
2. Temporarily increase max_connections (requires restart)
3. Scale up database replicas

## Long-term Fixes
- Implement connection pooling with PgBouncer
- Review application connection handling
- Add connection pool monitoring
""",
    },
    {
        "title": "Runbook: Service High Latency Troubleshooting",
        "doc_type": "runbook",
        "service": "auth-service",
        "content": """# High Latency Troubleshooting Runbook

## Symptoms
- p99 latency exceeding SLO (>200ms)
- Timeout errors in dependent services
- User complaints about slow response

## Diagnosis Steps
1. Check service metrics in Grafana:
   - Request latency percentiles
   - Error rates
   - Throughput

2. Check dependency health:
   - Database response times
   - Cache hit/miss rates
   - External API latencies

3. Review recent changes:
   - Deployments in last 24 hours
   - Configuration changes
   - Traffic pattern changes

## Common Causes and Fixes

### Cache Issues
- Low cache hit rate → Check cache configuration
- Cache service down → Failover to backup or disable caching

### Database Issues
- Slow queries → Run EXPLAIN ANALYZE
- Connection issues → Check connection pool

### Resource Exhaustion
- High CPU → Scale horizontally
- Memory pressure → Check for leaks, increase limits

## Escalation
If unable to resolve within 30 minutes, escalate to:
1. Service owner team
2. Platform team for infrastructure issues
""",
    },
    {
        "title": "Runbook: Redis Cache Operations",
        "doc_type": "runbook",
        "service": "redis-cache",
        "content": """# Redis Cache Operations Runbook

## Common Operations

### Check Redis Health
```bash
redis-cli -h redis-cache.internal ping
redis-cli -h redis-cache.internal info memory
redis-cli -h redis-cache.internal info stats
```

### Clear Specific Cache Pattern
```bash
redis-cli -h redis-cache.internal KEYS "session:*" | xargs redis-cli DEL
```

### Monitor Cache Hit Rate
```bash
redis-cli -h redis-cache.internal INFO stats | grep keyspace
```

## Troubleshooting

### High Memory Usage
1. Check memory fragmentation ratio
2. Identify large keys: `redis-cli --bigkeys`
3. Review eviction policy settings

### Cache Stampede Prevention
1. Implement jittered TTL in application
2. Enable request coalescing
3. Use probabilistic early expiration

### Connection Issues
1. Check maxclients setting
2. Review client timeout configurations
3. Monitor connection count over time

## Emergency Procedures
- Redis cluster failover: `redis-cli CLUSTER FAILOVER`
- Clear all cache (DANGEROUS): `redis-cli FLUSHALL`
""",
    },
    {
        "title": "Runbook: Kubernetes Pod OOM Troubleshooting",
        "doc_type": "runbook",
        "service": "notification-service",
        "content": """# Kubernetes Pod OOM Troubleshooting Runbook

## Symptoms
- Pod restarts with reason: OOMKilled
- Memory usage approaching limits
- Application becoming unresponsive

## Diagnosis Steps

### 1. Check Pod Status
```bash
kubectl describe pod <pod-name> -n production
kubectl logs <pod-name> -n production --previous
```

### 2. Analyze Memory Usage
```bash
kubectl top pod <pod-name> -n production
```

### 3. Generate Heap Dump (Java)
```bash
kubectl exec -it <pod-name> -- jmap -dump:format=b,file=/tmp/heap.hprof 1
kubectl cp <pod-name>:/tmp/heap.hprof ./heap.hprof
```

## Immediate Mitigation
1. Increase memory limits in deployment:
   ```yaml
   resources:
     limits:
       memory: "2Gi"  # Increase from 1Gi
   ```
2. Scale horizontally to distribute load
3. Restart affected pods

## Root Cause Investigation
1. Analyze heap dump for memory leaks
2. Review application logs for patterns
3. Check for unbounded caches or collections
4. Profile application under load

## Prevention
- Set appropriate resource requests and limits
- Implement memory usage alerts at 80%
- Regular profiling and load testing
""",
    },
    {
        "title": "Runbook: API Gateway Error Troubleshooting",
        "doc_type": "runbook",
        "service": "api-gateway",
        "content": """# API Gateway Error Troubleshooting Runbook

## Symptoms
- 5xx errors from gateway
- Connection refused to upstream services
- High latency or timeouts

## Initial Diagnosis

### 1. Check Gateway Health
```bash
curl -s http://api-gateway.internal/health
kubectl get pods -l app=api-gateway -n production
```

### 2. Identify Error Patterns
```bash
kubectl logs -l app=api-gateway -n production --tail=100 | grep -i error
```

### 3. Check Upstream Services
```bash
kubectl get svc -n production
kubectl get endpoints -n production
```

## Common Issues

### Connection Refused
- Check if upstream service is running
- Verify service discovery is working
- Check network policies

### 502 Bad Gateway
- Upstream service returning invalid response
- Health check failing
- SSL/TLS handshake issues

### 503 Service Unavailable
- All upstream pods are down
- Circuit breaker is open
- Rate limiting triggered

## Escalation Matrix
| Error Type | Owner Team | SLA |
|------------|------------|-----|
| Gateway config | Platform | 15 min |
| Upstream service | Service owner | 30 min |
| Network issues | Infrastructure | 1 hour |
""",
    },
]

INCIDENT_LOGS = [
    {
        "title": "Incident Log: Payment failure investigation 2024-01-28",
        "doc_type": "incident_log",
        "service": "payment-api",
        "trace_id": "abc123-def456",
        "level": "ERROR",
        "content": """[14:00:05] ALERT: Error rate exceeded 5% threshold for payment-api
[14:00:10] ERROR: Connection refused to db-primary:5432, attempt 1/3
[14:00:15] ERROR: Connection refused to db-primary:5432, attempt 2/3
[14:00:20] ERROR: Connection refused to db-primary:5432, attempt 3/3
[14:00:25] CRITICAL: PaymentProcessor.process() failed with NullPointerException
[14:01:00] INFO: On-call engineer @john.doe acknowledged alert
[14:05:00] INFO: Running diagnosis: checking database connection pool
[14:05:30] DEBUG: Connection pool status: 100/100 connections in use
[14:06:00] WARNING: Connection leak detected in PaymentProcessor class
[14:10:00] INFO: Applying mitigation: increasing connection pool to 150
""",
    },
    {
        "title": "Incident Log: Auth latency spike 2024-01-25",
        "doc_type": "incident_log",
        "service": "auth-service",
        "trace_id": "stu901-vwx234",
        "level": "WARN",
        "content": """[11:30:00] ALERT: p99 latency exceeded 200ms threshold (current: 450ms)
[11:30:05] INFO: Cache hit rate dropped to 15% (normal: 95%)
[11:30:10] DEBUG: Investigating cache configuration changes
[11:35:00] INFO: Found config change: TTL reduced from 3600s to 60s
[11:40:00] INFO: Initiating rollback of TTL configuration
[12:00:00] INFO: Rollback complete, monitoring latency
[12:15:00] INFO: Latency returned to normal (p99: 48ms)
[12:20:00] INFO: Incident marked as resolved
""",
    },
    {
        "title": "Incident Log: Cache stampede event 2024-01-22",
        "doc_type": "incident_log",
        "service": "redis-cache",
        "trace_id": None,
        "level": "ERROR",
        "content": """[04:00:00] CRITICAL: Database CPU at 100%
[04:00:05] ERROR: Query timeout: SELECT * FROM users WHERE id IN (...)
[04:00:10] ERROR: 50000 cache misses in last minute
[04:00:15] INFO: Auto-scaling triggered for db-primary
[04:05:00] INFO: 2 new database replicas starting
[04:10:00] INFO: Load distributed across replicas
[04:30:00] INFO: Database CPU stabilized at 60%
[05:00:00] INFO: Cache warm-up initiated
[06:00:00] INFO: Cache hit rate recovered to 85%
[07:00:00] INFO: Incident marked as resolved
""",
    },
    {
        "title": "Incident Log: Notification OOM crash 2024-01-29",
        "doc_type": "incident_log",
        "service": "notification-service",
        "trace_id": "mno345-pqr678",
        "level": "FATAL",
        "content": """[10:00:00] FATAL: Process killed by OOM killer (exit code 137)
[10:00:05] INFO: Pod notification-service-abc12 restarting
[10:00:30] INFO: Pod ready, resuming message processing
[10:25:00] WARNING: Memory usage at 85%
[10:30:00] FATAL: Process killed by OOM killer (exit code 137)
[10:30:05] INFO: Pod notification-service-abc12 restarting
[11:00:00] INFO: Investigation started, heap dump requested
[12:00:00] DEBUG: Heap analysis: 500MB retained by TemplateCache
[13:00:00] INFO: Root cause identified: unbounded template cache
[14:00:00] INFO: Fix deployed: LRU cache with 100 entry limit
""",
    },
    {
        "title": "Incident Log: Gateway connection errors 2024-01-29",
        "doc_type": "incident_log",
        "service": "api-gateway",
        "trace_id": "efg123-hij456",
        "level": "ERROR",
        "content": """[16:00:00] ALERT: 5xx error rate exceeded 10% for api-gateway
[16:00:05] ERROR: Connection refused to auth-service:8080
[16:00:10] ERROR: SSL handshake timeout with payment-api
[16:05:00] INFO: On-call engineer investigating
[16:10:00] DEBUG: Network policy review in progress
[16:15:00] INFO: Problematic pods identified: gateway-xyz89
[16:20:00] INFO: Pods restarted, monitoring error rate
[16:25:00] WARNING: Errors continuing from new pods
[16:30:00] INFO: Escalating to infrastructure team
[16:45:00] INFO: Network policy rolled back, errors decreasing
""",
    },
    {
        "title": "Incident Log: Database replication lag 2024-01-20",
        "doc_type": "incident_log",
        "service": "db-primary",
        "trace_id": None,
        "level": "WARN",
        "content": """[08:00:00] WARNING: Replication lag exceeded 5 seconds
[08:00:05] INFO: Primary database under heavy write load
[08:05:00] WARNING: Replication lag at 30 seconds
[08:10:00] INFO: Identified long-running transaction
[08:15:00] INFO: Transaction completed, lag recovering
[08:30:00] INFO: Replication lag returned to normal (<1s)
""",
    },
    {
        "title": "Incident Log: Message queue backup 2024-01-18",
        "doc_type": "incident_log",
        "service": "message-queue",
        "trace_id": None,
        "level": "WARN",
        "content": """[12:00:00] WARNING: Queue depth exceeded 10000 messages
[12:00:05] INFO: Consumer processing rate: 100 msg/s
[12:00:10] INFO: Producer rate: 500 msg/s
[12:05:00] INFO: Scaling up consumer replicas
[12:10:00] INFO: 5 additional consumers online
[12:30:00] INFO: Queue depth decreasing
[13:00:00] INFO: Queue depth normalized to 500
""",
    },
    {
        "title": "Incident Log: User service memory pressure 2024-01-15",
        "doc_type": "incident_log",
        "service": "user-service",
        "trace_id": None,
        "level": "WARN",
        "content": """[14:00:00] WARNING: GC pause time exceeded 100ms (current: 120ms)
[14:00:05] INFO: Memory usage at 80%
[14:05:00] WARNING: Frequent full GC events detected
[14:10:00] INFO: Heap size increased from 1GB to 2GB
[14:15:00] INFO: GC pause times normalizing
[14:30:00] INFO: Memory pressure resolved
""",
    },
    {
        "title": "Incident Log: Deployment rollback 2024-01-12",
        "doc_type": "incident_log",
        "service": "payment-api",
        "trace_id": None,
        "level": "WARN",
        "content": """[09:00:00] INFO: Deployment started: payment-api v4.0.1 -> v4.0.2
[09:05:00] INFO: Canary deployment at 10%
[09:10:00] WARNING: Error rate elevated in canary
[09:15:00] ALERT: Rollback initiated due to elevated errors
[09:20:00] INFO: Rollback complete: payment-api v4.0.2 -> v4.0.1
[09:25:00] INFO: Error rate normalized
[09:30:00] INFO: Post-mortem scheduled for deployment issue
""",
    },
    {
        "title": "Incident Log: Certificate expiry warning 2024-01-10",
        "doc_type": "incident_log",
        "service": "api-gateway",
        "trace_id": None,
        "level": "WARN",
        "content": """[00:00:00] WARNING: SSL certificate expires in 7 days
[00:00:05] INFO: Automated renewal initiated
[00:05:00] INFO: New certificate generated
[00:10:00] INFO: Certificate deployed to api-gateway
[00:15:00] INFO: Certificate validation successful
[00:20:00] INFO: Expiry warning cleared
""",
    },
]


async def get_embedding(text: str) -> list[float]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{settings.llm_base_url}/embeddings",
            json={"model": settings.embedding_model_name, "input": text},
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
        )
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]


async def clear_collection(client: QdrantClient):
    print("🗑️  Clearing existing collection...")
    try:
        client.delete_collection(settings.qdrant_collection)
        print("   Collection deleted.")
    except Exception:
        print("   Collection does not exist.")


async def create_collection(client: QdrantClient):
    print("📦 Creating collection...")
    client.create_collection(
        collection_name=settings.qdrant_collection,
        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
    )
    print(f"   Collection '{settings.qdrant_collection}' created.")


async def seed_documents(client: QdrantClient):
    all_docs = POSTMORTEMS + RUNBOOKS + INCIDENT_LOGS
    points = []

    print(f"📄 Processing {len(all_docs)} documents...")
    
    for i, doc in enumerate(all_docs):
        print(f"   [{i+1}/{len(all_docs)}] Embedding: {doc['title'][:50]}...")
        
        embed_text = f"{doc['title']}\n\n{doc['content']}"
        
        try:
            embedding = await get_embedding(embed_text)
        except Exception as e:
            print(f"   ⚠️  Failed to embed document: {e}")
            continue
        
        payload = {
            "title": doc["title"],
            "content": doc["content"],
            "doc_type": doc["doc_type"],
            "service": doc.get("service", ""),
        }
        
        if "incident_id" in doc:
            payload["incident_id"] = doc["incident_id"]
        if "severity" in doc:
            payload["severity"] = doc["severity"]
        if "trace_id" in doc:
            payload["trace_id"] = doc["trace_id"]
        if "level" in doc:
            payload["level"] = doc["level"]
        
        points.append(PointStruct(id=i, vector=embedding, payload=payload))
    
    print(f"\n📤 Uploading {len(points)} vectors to Qdrant...")
    client.upsert(collection_name=settings.qdrant_collection, points=points)
    print("   Upload complete.")


async def verify_data(client: QdrantClient):
    print("\n🔍 Verifying data...\n")
    
    collections = client.get_collections()
    collection_names = [c.name for c in collections.collections]
    
    if settings.qdrant_collection not in collection_names:
        print(f"   ❌ Collection '{settings.qdrant_collection}' not found!")
        return
    
    info = client.get_collection(settings.qdrant_collection)
    print(f"   Collection: {settings.qdrant_collection}")
    print(f"   Vector count: {info.points_count}")
    print(f"   Vector dimension: {info.config.params.vectors.size}")
    
    print("\n   Documents by type:")
    for doc_type in ["postmortem", "runbook", "incident_log"]:
        result = client.scroll(
            collection_name=settings.qdrant_collection,
            scroll_filter={
                "must": [{"key": "doc_type", "match": {"value": doc_type}}]
            },
            limit=100,
        )
        print(f"     {doc_type}: {len(result[0])}")
    
    print("\n   Sample search: 'database connection pool'")
    query_vector = await get_embedding("database connection pool exhaustion")
    results = client.query_points(
        collection_name=settings.qdrant_collection,
        query=query_vector,
        limit=3,
    )
    
    for hit in results.points:
        print(f"     [{hit.score:.3f}] {hit.payload['title'][:60]}...")
    
    print("\n✅ Verification complete!")


async def main():
    parser = argparse.ArgumentParser(description="Qdrant DevOps Seed Script")
    parser.add_argument("--verify", action="store_true", help="Verify data only")
    parser.add_argument("--clear", action="store_true", help="Clear collection")
    args = parser.parse_args()

    print(f"🔌 Connecting to Qdrant at {settings.qdrant_host}:{settings.qdrant_port}...")
    client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)

    try:
        client.get_collections()
        print("   Connected successfully!\n")

        if args.clear:
            await clear_collection(client)
        elif args.verify:
            await verify_data(client)
        else:
            await clear_collection(client)
            await create_collection(client)
            await seed_documents(client)
            await verify_data(client)
            
            print("\n🎉 Seeding complete!")

    except Exception as e:
        print(f"❌ Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
