"""
Hybrid Retrieval Nodes
Graph search (Neo4j) + Vector search (Qdrant)
"""

import asyncio
from typing import List, Dict, Any, Optional
from neo4j import AsyncGraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from langchain_openai import OpenAIEmbeddings

from config import settings
from app.state import GraphState, RetrievalResult, SlotInfo


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
            except Exception as e:
                print(f"Neo4j connection failed: {e}")
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
            except Exception as e:
                print(f"Qdrant connection failed: {e}")
                return None
        return cls._client


def get_embeddings():
    """Get embedding model (uses LM Studio or compatible endpoint)"""
    return OpenAIEmbeddings(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model="text-embedding-ada-002"  # Or your local model
    )


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
                # Build dynamic cypher query based on slots
                cypher = """
                MATCH (s:Service)-[r]-(related)
                WHERE s.name CONTAINS $service_hint OR s.name CONTAINS $error_hint
                RETURN s.name as service, type(r) as relationship, 
                       labels(related) as related_labels, related.name as related_name,
                       properties(related) as related_props
                LIMIT 10
                """
                
                service_hint = slots.service_name or ""
                error_hint = slots.error_type or ""
                
                result = await session.run(
                    cypher, 
                    service_hint=service_hint,
                    error_hint=error_hint
                )
                
                records = await result.data()
                
                for record in records:
                    results.append(RetrievalResult(
                        source="graph",
                        title=f"{record['service']} → {record['relationship']}",
                        content=f"Related: {record['related_name']}",
                        metadata={
                            "relationship": record["relationship"],
                            "related_labels": record["related_labels"]
                        },
                        confidence=0.85,
                        raw_data=record
                    ))
    except Exception as e:
        print(f"Graph search error: {e}")
    
    # Mock data fallback for demonstration
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
            # Generate query embedding
            embeddings = get_embeddings()
            query_vector = await embeddings.aembed_query(query)
            
            # Build filter based on slots
            filter_conditions = []
            if slots.service_name:
                filter_conditions.append(
                    FieldCondition(
                        key="service",
                        match=MatchValue(value=slots.service_name)
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
                    content=hit.payload.get("content", ""),
                    metadata=hit.payload,
                    confidence=hit.score,
                    raw_data=hit.payload
                ))
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
    error = slots.error_type or "timeout"
    
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
