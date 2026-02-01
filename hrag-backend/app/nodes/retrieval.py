"""
Hybrid Retrieval Nodes
Graph search (Neo4j) + Vector search (Qdrant)
"""

import asyncio
from typing import List, Optional, Any

import httpx
from neo4j import AsyncGraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchText

from app.domain_init import get_active_domain
from app.state import DynamicSlotInfo, GraphState, RetrievalResult, SlotInfo
from app.schema_registry import SchemaRegistry
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from config import settings

# Embedding dimension for embeddinggemma-300m (768 dimensions)
EMBEDDING_DIM = 768


def get_llm():
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model_name,
        temperature=0.0,
    )


async def generate_cypher_query(query: str, schema_str: str, slots: DynamicSlotInfo) -> str:
    """Generate Cypher query using LLM and Schema."""
    
    llm = get_llm()
    
    system_prompt = """You are a Neo4j Cypher expert.
Your task is to generate a Cypher query to answer the user's question based on the provided Graph Schema.

# Graph Schema
{schema}

# Rules
1. Use ONLY the node labels and relationship types defined in the schema.
2. Do not use markdown backticks in your output. Just return the raw Cypher query.
3. Use case-insensitive string matching for properties (e.g. `toLower(n.name) CONTAINS toLower('value')`).
4. Limit results to 20 unless specified otherwise.
5. Return readable properties to help user understand the context.
"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "User Query: {query}\n\nExtracted Slots: {slots}"),
    ])
    
    chain = prompt | llm
    
    response = await chain.ainvoke({
        "schema": schema_str,
        "query": query,
        "slots": slots.to_display_string() # Assuming to_display_string exists, otherwise str(slots)
    })
    
    cypher = response.content.replace("```cypher", "").replace("```", "").strip()
    return cypher


class Neo4jClient:
    """Neo4j graph database client"""

    _driver = None

    @classmethod
    async def get_driver(cls):
        if cls._driver is None:
            try:
                cls._driver = AsyncGraphDatabase.driver(
                    settings.neo4j_uri,
                    auth=(settings.neo4j_user, settings.neo4j_password),
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
                    host=settings.qdrant_host, port=settings.qdrant_port
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
    
    Raises:
        RuntimeError: If embedding generation fails.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{settings.llm_base_url}/embeddings",
            json={"model": settings.embedding_model_name, "input": text},
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
        )
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]


async def graph_search_node(state: GraphState) -> GraphState:
    """
    Graph Search Node (Neo4j)

    Queries the knowledge graph based on active domain configuration.
    """
    # Handle legacy slots
    slots = state.get("slots")
    if isinstance(slots, SlotInfo):
        slots = slots.to_dynamic()
    elif slots is None:
        slots = DynamicSlotInfo()
        
    query = state.get("query", "")
    current_domain = get_active_domain()
    
    if not current_domain:
        print("[GraphSearch] Warning: No active domain found, skipping search.")
        return {**state, "graph_results": []}

    results: List[RetrievalResult] = []

    try:
        driver = await Neo4jClient.get_driver()

        if driver:
            async with driver.session() as session:
                # Prepare query parameters
                params = {"hint": query}
                # Add all slots as parameters
                params.update(slots.get_filled_slots())
                
                
                # Determine which Cypher query to run
                cypher = ""
                
                # Try to generate dynamic query first
                if current_domain.schema_name:
                    schema = SchemaRegistry.get_schema(current_domain.schema_name)
                    if schema and schema.extraction_prompt:
                        print(f"[GraphSearch] Generating dynamic Cypher for schema: {current_domain.schema_name}")
                        try:
                            cypher = await generate_cypher_query(query, schema.extraction_prompt, slots)
                            print(f"[GraphSearch] Generated Cypher: {cypher}")
                        except Exception as gen_err:
                             print(f"[GraphSearch] Cypher generation failed: {gen_err}")
                
                # Fallback to configured primary search
                if not cypher:
                     print("[GraphSearch] Using fallback primary_search query.")
                     cypher = current_domain.graph_queries.primary_search
                
                if not cypher:
                    print("[GraphSearch] Warning: No efficient query source found.")
                    return {**state, "graph_results": []}

                result = await session.run(cypher, **params)
                records = await result.data()

                for record in records:
                    # Construct title/content dynamically based on returned fields
                    # We expect the query to return readable fields
                    
                    # Try to find a 'name' or 'subject' or 'title' for the result title
                    title_candidates = ["subject", "name", "title", "id", "event_id"]
                    title = "Graph Result"
                    for key in title_candidates:
                        if key in record:
                            title = f"{key.title()}: {record[key]}"
                            break
                            
                    # Everything else goes into content/metadata
                    content_parts = []
                    for k, v in record.items():
                        if k not in title_candidates and v:
                            if isinstance(v, list):
                                v = ", ".join([str(i) for i in v])
                            content_parts.append(f"{k}: {v}")
                    
                    content = "\n".join(content_parts)
                    
                    results.append(
                        _make_serializable(RetrievalResult(
                            source="graph",
                            title=title,
                            content=content,
                            metadata=record,
                            confidence=0.85,  # Heuristic confidence
                            raw_data=record,
                        ).model_dump())
                    )

    except Exception as e:
        print(f"[GraphSearch] Error: {e}")
        # Don't fail the whole workflow, just return empty results
        # raise RuntimeError(f"Graph search failed: {e}") from e

    return {**state, "graph_results": results}


def _make_serializable(obj: Any) -> Any:
    """Recursively convert Neo4j types (DateTime, etc.) to strings."""
    from neo4j.time import DateTime, Date, Time, Duration
    
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_make_serializable(v) for v in obj]
    elif isinstance(obj, (DateTime, Date, Time, Duration)):
        return str(obj)
    else:
        return obj


async def vector_search_node(state: GraphState) -> GraphState:
    """
    Vector Search Node (Qdrant)

    Semantic search over document embeddings with dynamic filtering.
    """
    query = state.get("query", "")
    
    # Handle legacy slots
    slots = state.get("slots")
    if isinstance(slots, SlotInfo):
        slots = slots.to_dynamic()
    elif slots is None:
        slots = DynamicSlotInfo()

    current_domain = get_active_domain()
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

                # Build filter based on domain config and slots
                filter_conditions = []
                
                if current_domain:
                    filled_slots = slots.get_filled_slots()
                    for field in current_domain.vector_filter_fields:
                        if field in filled_slots:
                             # Add filter condition
                             # Assumes slot name matches Qdrant payload field name
                            filter_conditions.append(
                                FieldCondition(
                                    key=field, 
                                    match=MatchText(text=str(filled_slots[field]))
                                )
                            )

                search_filter = (
                    Filter(must=filter_conditions) if filter_conditions else None
                )

                # Execute search using query_points (Qdrant client >= 1.10)
                try:
                    search_results = client.query_points(
                        collection_name=settings.qdrant_collection,
                        query=query_vector,
                        limit=5,
                        query_filter=search_filter,
                    )

                    for hit in search_results.points:
                        results.append(
                            _make_serializable(RetrievalResult(
                                source="vector",
                                title=hit.payload.get("title", "Document"),
                                content=hit.payload.get("content", "")[:300] + "...",
                                metadata={
                                    k: v for k, v in hit.payload.items() 
                                    if k not in ["content", "title", "text"]
                                },
                                confidence=float(hit.score),
                                raw_data=hit.payload,
                            ).model_dump())
                        )
                except Exception as search_err:
                    print(f"[VectorSearch] Query failed: {search_err}")
                    
            else:
                 print(f"[VectorSearch] Collection '{settings.qdrant_collection}' not found.")
        else:
            print("[VectorSearch] Client not available")

    except Exception as e:
         print(f"[VectorSearch] Error: {e}")
         # Don't fail the whole workflow

    return {**state, "vector_results": results}


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
        "vector_results": vector_state.get("vector_results", []),
    }

