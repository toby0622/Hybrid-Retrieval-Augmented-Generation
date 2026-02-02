import asyncio
from typing import Any, List, Optional

import httpx
from app.domain_init import get_active_domain
from app.schema_registry import SchemaRegistry
from app.state import DynamicSlotInfo, GraphState, RetrievalResult, SlotInfo
from config import settings
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from neo4j import AsyncGraphDatabase
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchText

EMBEDDING_DIM = 768


def get_llm():
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model_name,
        temperature=0.0,
    )


async def generate_cypher_query(
    query: str, schema_str: str, slots: DynamicSlotInfo
) -> str:
    llm = get_llm()

    system_prompt = """<!-- 1. Task Context -->
You are a Neo4j Cypher expert.
Your task is to generate a Cypher query to answer the user's question based on the provided Graph Schema.

<!-- 2. Tone Context -->
Be precise and technical. Prioritize query correctness over complexity.
Generate safe, read-only queries. Never use DELETE, REMOVE, or SET clauses.

<!-- 3. Background Data -->
# Graph Schema
{schema}

<!-- 4. Detailed Task Description & Rules -->
# Rules
1. Use ONLY the node labels and relationship types defined in the schema.
2. Do not use markdown backticks in your output. Just return the raw Cypher query.
3. Use case-insensitive string matching for properties (e.g. `toLower(n.name) CONTAINS toLower('value')`).
4. Limit results to 20 unless specified otherwise.
5. Return readable properties to help user understand the context.

# Directionality Hints
- **Impact Analysis** (e.g., "What happens if X fails?"): Look for incoming DEPENDS_ON relationships. `MATCH (affected:Service)-[:DEPENDS_ON]->(root:Service {{name: 'X'}}) RETURN affected`
- **Dependency Check** (e.g., "What does X depend on?"): Look for outgoing DEPENDS_ON relationships. `MATCH (source:Service {{name: 'X'}})-[:DEPENDS_ON]->(dep:Service) RETURN dep`

<!-- 5. Examples -->
<examples>
  <example>
    <query>What services depend on Redis?</query>
    <cypher>MATCH (s:Service)-[:DEPENDS_ON]->(r:Service {{name: 'Redis'}}) RETURN s.name AS dependent_service LIMIT 20</cypher>
  </example>
  <example>
    <query>Show all relationships for Auth-Service</query>
    <cypher>MATCH (a:Service {{name: 'Auth-Service'}})-[r]-(b) RETURN type(r) AS relationship, labels(b) AS node_type, b.name AS connected_to LIMIT 20</cypher>
  </example>
</examples>

<!-- 9. Output Formatting -->
Output: Raw Cypher query only. No markdown. No explanation.
"""

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "User Query: {query}\n\nExtracted Slots: {slots}"),
            ("ai", "MATCH "),
        ]
    )

    chain = prompt | llm

    response = await chain.ainvoke(
        {"schema": schema_str, "query": query, "slots": slots.to_display_string()}
    )

    cypher = response.content.replace("```cypher", "").replace("```", "").strip()
    return cypher


class Neo4jClient:
    _driver = None

    @classmethod
    async def get_driver(cls):
        if cls._driver is None:
            try:
                cls._driver = AsyncGraphDatabase.driver(
                    settings.neo4j_uri,
                    auth=(settings.neo4j_user, settings.neo4j_password),
                )
                async with cls._driver.session() as session:
                    await session.run("RETURN 1")
            except Exception as e:
                cls._driver = None
                return None
        return cls._driver

    @classmethod
    async def close(cls):
        if cls._driver:
            await cls._driver.close()
            cls._driver = None


class QdrantClientWrapper:
    _client: Optional[QdrantClient] = None

    @classmethod
    def get_client(cls) -> Optional[QdrantClient]:
        if cls._client is None:
            try:
                cls._client = QdrantClient(
                    host=settings.qdrant_host, port=settings.qdrant_port
                )
                cls._client.get_collections()
            except Exception as e:
                cls._client = None
                return None
        return cls._client


async def get_embedding(text: str) -> List[float]:
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
    slots = state.get("slots")
    if isinstance(slots, SlotInfo):
        slots = slots.to_dynamic()
    elif slots is None:
        slots = DynamicSlotInfo()

    query = state.get("query", "")
    current_domain = get_active_domain()

    if not current_domain:
        return {**state, "graph_results": []}

    results: List[RetrievalResult] = []

    try:
        driver = await Neo4jClient.get_driver()

        if driver:
            async with driver.session() as session:
                params = {"hint": query}
                params.update(slots.get_filled_slots())

                cypher = ""

                if current_domain.schema_name:
                    schema = SchemaRegistry.get_schema(current_domain.schema_name)
                    if schema and schema.extraction_prompt:
                        try:
                            cypher = await generate_cypher_query(
                                query, schema.extraction_prompt, slots
                            )
                        except Exception as gen_err:
                            pass

                if not cypher:
                    cypher = current_domain.graph_queries.primary_search

                if not cypher:
                    return {**state, "graph_results": []}

                result = await session.run(cypher, **params)
                records = await result.data()

                for record in records:
                    title_candidates = ["subject", "name", "title", "id", "event_id"]
                    title = "Graph Result"
                    for key in title_candidates:
                        if key in record:
                            title = f"{key.title()}: {record[key]}"
                            break

                    content_parts = []
                    for k, v in record.items():
                        if k not in title_candidates and v:
                            if isinstance(v, list):
                                v = ", ".join([str(i) for i in v])
                            content_parts.append(f"{k}: {v}")

                    content = "\n".join(content_parts)

                    results.append(
                        _make_serializable(
                            RetrievalResult(
                                source="graph",
                                title=title,
                                content=content,
                                metadata=record,
                                confidence=0.85,
                                raw_data=record,
                            ).model_dump()
                        )
                    )

    except Exception as e:
        pass

    return {**state, "graph_results": results}


def _make_serializable(obj: Any) -> Any:
    from neo4j.time import Date, DateTime, Duration, Time

    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_make_serializable(v) for v in obj]
    elif isinstance(obj, (DateTime, Date, Time, Duration)):
        return str(obj)
    else:
        return obj


async def vector_search_node(state: GraphState) -> GraphState:
    query = state.get("query", "")

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
            collections = client.get_collections()
            collection_names = [c.name for c in collections.collections]

            if settings.qdrant_collection in collection_names:
                query_vector = await get_embedding(query)

                filter_conditions = []

                if current_domain:
                    filled_slots = slots.get_filled_slots()
                    for field in current_domain.vector_filter_fields:
                        if field in filled_slots:
                            filter_conditions.append(
                                FieldCondition(
                                    key=field,
                                    match=MatchText(text=str(filled_slots[field])),
                                )
                            )

                search_filter = (
                    Filter(must=filter_conditions) if filter_conditions else None
                )

                try:
                    search_results = client.query_points(
                        collection_name=settings.qdrant_collection,
                        query=query_vector,
                        limit=5,
                        query_filter=search_filter,
                    )

                    for hit in search_results.points:
                        results.append(
                            _make_serializable(
                                RetrievalResult(
                                    source="vector",
                                    title=hit.payload.get("title", "Document"),
                                    content=hit.payload.get("content", "")[:300]
                                    + "...",
                                    metadata={
                                        k: v
                                        for k, v in hit.payload.items()
                                        if k not in ["content", "title", "text"]
                                    },
                                    confidence=float(hit.score),
                                    raw_data=hit.payload,
                                ).model_dump()
                            )
                        )
                except Exception as search_err:
                    pass

            else:
                pass
        else:
            pass

    except Exception as e:
        pass

    return {**state, "vector_results": results}


async def hybrid_retrieval_node(state: GraphState) -> GraphState:
    graph_task = asyncio.create_task(graph_search_node(state))
    vector_task = asyncio.create_task(vector_search_node(state))

    graph_state = await graph_task
    vector_state = await vector_task

    return {
        **state,
        "graph_results": graph_state.get("graph_results", []),
        "vector_results": vector_state.get("vector_results", []),
    }
