"""
Hybrid Retrieval Nodes
Graph search (Neo4j) + Vector search (Qdrant)
"""

import asyncio
from typing import List, Optional
import httpx
from neo4j import AsyncGraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchText

from config import settings
from app.state import GraphState, RetrievalResult, SlotInfo


# Embedding dimension for embeddinggemma-300m (768 dimensions)
EMBEDDING_DIM = 768


class Neo4jClient:
    """Neo4j graph database client"""
    
    _driver = None
    
    @classmethod
    async def get_driver(cls):
        if cls._driver is None:
            try:
                cls._driver = AsyncGraphDatabase.driver(
                    settings.neo4j_uri,
                    auth=(settings.neo4j_user, settings.neo4j_password)
                )
                # Test connection
                async with cls._driver.session() as session:
                    await session.run("RETURN 1")
                print("✅ Neo4j connected successfully")
            except Exception as e:
                print(f"❌ Neo4j connection failed: {e}")
                cls._driver = None
                return None
        return cls._driver
    
    @classmethod
    async def close(cls):
        if cls._driver:
            await cls._driver.close()
            cls._driver = None


class QdrantClientWrapper:
    """Qdrant vector database client"""
    
    _client: Optional[QdrantClient] = None
    
    @classmethod
    def get_client(cls) -> Optional[QdrantClient]:
        if cls._client is None:
            try:
                cls._client = QdrantClient(
                    host=settings.qdrant_host,
                    port=settings.qdrant_port
                )
                # Test connection
                cls._client.get_collections()
                print("✅ Qdrant connected successfully")
            except Exception as e:
                print(f"❌ Qdrant connection failed: {e}")
                cls._client = None
                return None
        return cls._client


async def get_embedding(text: str) -> List[float]:
    """
    Get embedding from LM Studio embedding model.
    Uses the OpenAI-compatible /v1/embeddings endpoint.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.llm_base_url}/embeddings",
                json={
                    "model": settings.embedding_model_name,
                    "input": text
                },
                headers={"Authorization": f"Bearer {settings.llm_api_key}"}
            )
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]
    except Exception as e:
        print(f"Embedding error: {e}")
        # Fallback to hash-based embedding for demo
        import numpy as np
        np.random.seed(hash(text.lower()) % 10000)
        embedding = np.random.randn(EMBEDDING_DIM).astype(np.float32)
        return (embedding / np.linalg.norm(embedding)).tolist()


async def graph_search_node(state: GraphState) -> GraphState:
    """
    Graph Search Node (Neo4j)
    
    Queries the knowledge graph for topology and relationships.
    Falls back to mock data if Neo4j is unavailable.
    """
    slots = state.get("slots", SlotInfo())
    query = state.get("query", "")
    
    results: List[RetrievalResult] = []
    
    try:
        driver = await Neo4jClient.get_driver()
        
        if driver:
            async with driver.session() as session:
                # Query 1: Find services and their relationships
                service_hint = slots.service_name or ""
                
                # If we have a service hint, search for it
                if service_hint:
                    cypher = """
                    MATCH (s:Service)-[r]-(related)
                    WHERE toLower(s.name) CONTAINS toLower($service_hint)
                    RETURN s.name as service, s.version as version, 
                           type(r) as relationship, 
                           labels(related)[0] as related_type,
                           related.name as related_name,
                           properties(related) as related_props
                    LIMIT 10
                    """
                else:
                    # Default: get recent events and affected services
                    cypher = """
                    MATCH (e:Event)-[r:AFFECTS|TRIGGERED_BY]-(s:Service)
                    RETURN e.event_id as event_id, e.description as description,
                           e.severity as severity, e.timestamp as timestamp,
                           type(r) as relationship, s.name as service,
                           s.version as version
                    ORDER BY e.timestamp DESC
                    LIMIT 5
                    """
                
                result = await session.run(cypher, service_hint=service_hint)
                records = await result.data()
                
                for record in records:
                    if "event_id" in record:
                        # Event result
                        results.append(RetrievalResult(
                            source="graph",
                            title=f"Event: {record['event_id']}",
                            content=f"{record['description']} (affects {record['service']})",
                            metadata={
                                "event_id": record["event_id"],
                                "severity": record.get("severity"),
                                "timestamp": record.get("timestamp")
                            },
                            confidence=0.90,
                            raw_data=record
                        ))
                    else:
                        # Service relationship result
                        results.append(RetrievalResult(
                            source="graph",
                            title=f"{record['service']} → {record['relationship']}",
                            content=f"Related to {record['related_type']}: {record['related_name']}",
                            metadata={
                                "service": record["service"],
                                "version": record.get("version"),
                                "relationship": record["relationship"],
                                "related_type": record.get("related_type")
                            },
                            confidence=0.85,
                            raw_data=record
                        ))
                
                # Query 2: If searching for config issues
                if "config" in query.lower() or "pool" in query.lower() or "timeout" in query.lower():
                    config_cypher = """
                    MATCH (c:Config)-[:CONFIGURES]->(s:Service)
                    RETURN c.name as config_name, c.max_pool_size as max_pool_size,
                           c.timeout_ms as timeout_ms, s.name as service
                    """
                    config_result = await session.run(config_cypher)
                    config_records = await config_result.data()
                    
                    for record in config_records:
                        results.append(RetrievalResult(
                            source="graph",
                            title=f"Config: {record['config_name']}",
                            content=f"Service: {record['service']}, Pool Size: {record['max_pool_size']}, Timeout: {record['timeout_ms']}ms",
                            metadata=record,
                            confidence=0.88,
                            raw_data=record
                        ))
                        
    except Exception as e:
        print(f"Graph search error: {e}")
    
    # Fallback to mock if no results
    if not results:
        results = _get_mock_graph_results(slots)
    
    return {
        **state,
        "graph_results": results
    }


async def vector_search_node(state: GraphState) -> GraphState:
    """
    Vector Search Node (Qdrant)
    
    Semantic search over document embeddings.
    Falls back to mock data if Qdrant is unavailable.
    """
    query = state.get("query", "")
    slots = state.get("slots", SlotInfo())
    
    results: List[RetrievalResult] = []
    
    try:
        client = QdrantClientWrapper.get_client()
        
        if client:
            # Check if collection exists
            collections = client.get_collections()
            collection_names = [c.name for c in collections.collections]
            
            if settings.qdrant_collection in collection_names:
                # Generate query embedding using LM Studio
                query_vector = await get_embedding(query)
                
                # Build filter based on slots
                filter_conditions = []
                if slots.service_name:
                    filter_conditions.append(
                        FieldCondition(
                            key="service",
                            match=MatchText(text=slots.service_name)
                        )
                    )
                
                search_filter = Filter(must=filter_conditions) if filter_conditions else None
                
                # Execute search
                search_results = client.search(
                    collection_name=settings.qdrant_collection,
                    query_vector=query_vector,
                    limit=5,
                    query_filter=search_filter
                )
                
                for hit in search_results:
                    results.append(RetrievalResult(
                        source="vector",
                        title=hit.payload.get("title", "Document"),
                        content=hit.payload.get("content", "")[:300] + "...",
                        metadata={
                            "document_type": hit.payload.get("document_type", ""),
                            "service": hit.payload.get("service", ""),
                            "tags": hit.payload.get("tags", [])
                        },
                        confidence=float(hit.score),
                        raw_data=hit.payload
                    ))
            else:
                print(f"Collection '{settings.qdrant_collection}' not found. Run init_db.py first.")
                
    except Exception as e:
        print(f"Vector search error: {e}")
    
    # Mock data fallback
    if not results:
        results = _get_mock_vector_results(slots)
    
    return {
        **state,
        "vector_results": results
    }


async def hybrid_retrieval_node(state: GraphState) -> GraphState:
    """
    Hybrid Retrieval Node
    
    Runs graph and vector search in parallel and aggregates results.
    """
    # Run both searches in parallel
    graph_task = asyncio.create_task(graph_search_node(state))
    vector_task = asyncio.create_task(vector_search_node(state))
    
    graph_state = await graph_task
    vector_state = await vector_task
    
    # Merge results
    return {
        **state,
        "graph_results": graph_state.get("graph_results", []),
        "vector_results": vector_state.get("vector_results", [])
    }


def _get_mock_graph_results(slots: SlotInfo) -> List[RetrievalResult]:
    """Generate mock graph results for demonstration"""
    service = slots.service_name or "PaymentService"
    
    return [
        RetrievalResult(
            source="graph",
            title=f"{service} Deployment",
            content=f"v2.4.1-hotfix deployed @ 09:15 UTC",
            metadata={
                "node": service,
                "relationship": "DEPLOYED_ON",
                "properties": {"version": "v2.4.1-hotfix", "timestamp": "2025-01-28T09:15:00Z"}
            },
            confidence=0.92,
            raw_data={
                "node": service,
                "relationship": "DEPLOYED_ON", 
                "properties": {"version": "v2.4.1-hotfix"}
            }
        ),
        RetrievalResult(
            source="graph",
            title=f"{service} Dependencies",
            content="Depends on: Redis-Cache, PostgreSQL-Primary",
            metadata={
                "dependencies": ["Redis-Cache", "PostgreSQL-Primary"]
            },
            confidence=0.88,
            raw_data={"dependencies": ["Redis-Cache", "PostgreSQL-Primary"]}
        )
    ]


def _get_mock_vector_results(slots: SlotInfo) -> List[RetrievalResult]:
    """Generate mock vector results for demonstration"""
    
    return [
        RetrievalResult(
            source="vector",
            title="Post-Mortem #402: HikariCP Pool Exhaustion",
            content="Root Cause: Connection pool size was reset to default (10) after deployment. Under load, this caused connection exhaustion and timeout errors.",
            metadata={
                "document_type": "post_mortem",
                "date": "2025-01-15"
            },
            confidence=0.89,
            raw_data="""**Post-Mortem #402 Summary**
Root Cause: HikariCP pool size reset during deployment.
Resolution: Updated config to maintain pool-size=50.
Prevention: Added config validation in CI/CD pipeline."""
        ),
        RetrievalResult(
            source="vector",
            title="SOP: Database Connection Troubleshooting",
            content="Steps for diagnosing connection issues: 1. Check HikariCP metrics 2. Verify pool size configuration 3. Review recent deployments",
            metadata={
                "document_type": "sop",
                "category": "database"
            },
            confidence=0.82,
            raw_data="Standard Operating Procedure for database connection troubleshooting..."
        )
    ]
