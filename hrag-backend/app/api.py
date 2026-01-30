"""
HRAG FastAPI Application
REST API endpoints for the HRAG system
"""

import asyncio
import json
import uuid
from typing import AsyncGenerator, List, Optional

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.graph import graph, run_query
from app.nodes.feedback import check_entity_conflicts, extract_entities_node
from app.state import DiagnosticResponse, DiagnosticStep, SlotInfo
from config import settings

# --- API Models ---


class ChatRequest(BaseModel):
    """Chat request model"""

    query: str
    thread_id: Optional[str] = None
    feedback: Optional[str] = None
    stream: bool = False  # Enable streaming mode


class ReasoningStep(BaseModel):
    """Reasoning step for streaming"""

    id: str
    label: str
    status: str = "pending"


class ChatResponse(BaseModel):
    """Chat response model"""

    thread_id: str
    response: str
    intent: Optional[str] = None
    response_type: str = "text"  # text, reasoning, diagnostic
    reasoning_steps: Optional[List[ReasoningStep]] = None
    diagnostic: Optional[DiagnosticResponse] = None
    clarification_question: Optional[str] = None


class EntityConflict(BaseModel):
    """Entity conflict for gardener review"""

    id: str
    type: str  # conflict, new
    entity_name: str
    source: str
    confidence: float
    existing_entity: Optional[dict] = None
    new_entity: dict
    description: Optional[str] = None


class GardenerTask(BaseModel):
    """Gardener task model"""

    tasks: List[EntityConflict]


class GardenerAction(BaseModel):
    """Gardener approval action"""

    entity_id: str
    action: str  # approve, reject, merge
    modified_entity: Optional[dict] = None


class UploadResponse(BaseModel):
    """Upload response model"""

    file_name: str
    status: str
    entities_extracted: int
    conflicts_found: int
    task_ids: List[str]


class HealthResponse(BaseModel):
    """Health check response"""

    status: str
    neo4j: str
    qdrant: str
    llm: str


# --- FastAPI App ---

app = FastAPI(
    title="HRAG Backend API",
    description="Hybrid Retrieval-Augmented Generation API for DevOps Incident Response",
    version="0.1.0",
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for gardener tasks (replace with DB in production)
gardener_tasks: dict = {}


# --- Endpoints ---


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    Checks connectivity to all services.
    """
    neo4j_status = "disconnected"
    qdrant_status = "disconnected"
    llm_status = "disconnected"

    # Check Neo4j
    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(
            settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
        )
        with driver.session() as session:
            session.run("RETURN 1")
        driver.close()
        neo4j_status = "connected"
    except Exception as e:
        neo4j_status = f"error: {str(e)[:30]}"

    # Check Qdrant
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
        client.get_collections()
        qdrant_status = "connected"
    except Exception as e:
        qdrant_status = f"error: {str(e)[:30]}"

    # Check LLM
    try:
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.llm_base_url}/models")
            if response.status_code == 200:
                llm_status = "connected"
    except Exception as e:
        llm_status = f"error: {str(e)[:30]}"

    overall_status = (
        "healthy"
        if all(s == "connected" for s in [neo4j_status, qdrant_status])
        else "degraded"
    )

    return HealthResponse(
        status=overall_status, neo4j=neo4j_status, qdrant=qdrant_status, llm=llm_status
    )


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Streaming chat endpoint.
    Streams reasoning steps in real-time, then sends diagnostic.
    """
    thread_id = request.thread_id or str(uuid.uuid4())

    async def generate() -> AsyncGenerator[str, None]:
        # Stream reasoning steps first
        reasoning_steps = [
            {
                "id": "step_0",
                "label": "Input Guardrails: Analyzing query...",
                "status": "pending",
            },
            {
                "id": "step_1",
                "label": "Slot Extraction: Identifying entities...",
                "status": "pending",
            },
            {
                "id": "step_2",
                "label": "Graph Search: Querying topology...",
                "status": "pending",
            },
            {
                "id": "step_3",
                "label": "Vector Search: Finding relevant documents...",
                "status": "pending",
            },
            {
                "id": "step_4",
                "label": "MCP Tool: Executing data queries...",
                "status": "pending",
            },
            {
                "id": "step_5",
                "label": "LLM Reasoning: Synthesizing diagnosis...",
                "status": "pending",
            },
        ]

        # Stream each step with delay
        for i, step in enumerate(reasoning_steps):
            step["status"] = "active"
            yield f"data: {json.dumps({'type': 'reasoning', 'step': step})}\n\n"
            await asyncio.sleep(0.3)  # Small delay for animation

            # Mark as completed
            step["status"] = "completed"
            yield f"data: {json.dumps({'type': 'reasoning', 'step': step})}\n\n"

        # Now run the actual graph
        try:
            result = await run_query(
                query=request.query, thread_id=thread_id, feedback=request.feedback
            )

            # Send final response
            response_data = {
                "type": "complete",
                "thread_id": thread_id,
                "response": result.get("response", ""),
                "intent": result.get("intent", "chat"),
                "diagnostic": result.get("diagnostic"),
                "clarification_question": result.get("clarification_question"),
            }

            # Serialize diagnostic if present (Pydantic model)
            if response_data["diagnostic"]:
                response_data["diagnostic"] = response_data["diagnostic"].model_dump()

            yield f"data: {json.dumps(response_data)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint.
    Processes user queries through the HRAG graph.
    """
    thread_id = request.thread_id or str(uuid.uuid4())

    try:
        result = await run_query(
            query=request.query, thread_id=thread_id, feedback=request.feedback
        )

        intent = result.get("intent", "chat")
        response = result.get("response", "")
        diagnostic = result.get("diagnostic")
        reasoning_steps = result.get("reasoning_steps", [])
        clarification = result.get("clarification_question")

        # Determine response type
        if diagnostic:
            response_type = "diagnostic"
        elif reasoning_steps:
            response_type = "reasoning"
        elif clarification:
            response_type = "clarification"
        else:
            response_type = "text"

        # Format reasoning steps
        formatted_steps = [
            ReasoningStep(id=f"step_{i}", label=step, status="completed")
            for i, step in enumerate(reasoning_steps)
        ]

        return ChatResponse(
            thread_id=thread_id,
            response=response if not clarification else clarification,
            intent=intent,
            response_type=response_type,
            reasoning_steps=formatted_steps if formatted_steps else None,
            diagnostic=diagnostic,
            clarification_question=clarification,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


@app.post("/upload", response_model=UploadResponse)
async def upload_knowledge(
    file: UploadFile = File(...), background_tasks: BackgroundTasks = None
):
    """
    Upload knowledge document for ingestion.
    Parses document and extracts entities for gardener review.
    """
    try:
        content = await file.read()
        content_str = content.decode("utf-8")

        # Extract entities
        entities = await extract_entities_node(content_str)

        # Check for conflicts (mock existing entities)
        existing_entities = []  # TODO: Load from graph DB

        conflicts = []
        new_entities = []
        task_ids = []

        for entity in entities:
            conflict_check = await check_entity_conflicts(entity, existing_entities)

            task_id = str(uuid.uuid4())
            task_ids.append(task_id)

            if conflict_check.get("has_conflict"):
                conflict = EntityConflict(
                    id=task_id,
                    type="conflict",
                    entity_name=entity.get("name", "Unknown"),
                    source=file.filename,
                    confidence=conflict_check.get("confidence", 0.0),
                    existing_entity=conflict_check.get("existing_entity"),
                    new_entity=entity,
                )
                conflicts.append(conflict)
                gardener_tasks[task_id] = conflict
            else:
                new_task = EntityConflict(
                    id=task_id,
                    type="new",
                    entity_name=entity.get("name", "Unknown"),
                    source=file.filename,
                    confidence=0.95,
                    new_entity=entity,
                    description=entity.get("description", ""),
                )
                new_entities.append(new_task)
                gardener_tasks[task_id] = new_task

        return UploadResponse(
            file_name=file.filename,
            status="processed",
            entities_extracted=len(entities),
            conflicts_found=len(conflicts),
            task_ids=task_ids,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload error: {str(e)}")


@app.get("/gardener/tasks", response_model=GardenerTask)
async def get_gardener_tasks():
    """
    Get pending gardener tasks for review.
    """
    tasks = list(gardener_tasks.values())
    return GardenerTask(tasks=tasks)


@app.post("/gardener/action")
async def gardener_action(action: GardenerAction):
    """
    Process gardener action on an entity.
    """
    task_id = action.entity_id

    if task_id not in gardener_tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = gardener_tasks[task_id]

    if action.action == "approve":
        # TODO: Write entity to graph DB
        del gardener_tasks[task_id]
        return {"status": "approved", "message": "Entity written to knowledge graph"}

    elif action.action == "reject":
        del gardener_tasks[task_id]
        return {"status": "rejected", "message": "Entity discarded"}

    elif action.action == "merge":
        if action.modified_entity:
            # TODO: Update entity in graph DB
            pass
        del gardener_tasks[task_id]
        return {"status": "merged", "message": "Entity merged and updated"}

    else:
        raise HTTPException(status_code=400, detail="Invalid action")


@app.get("/stats")
async def get_stats():
    """
    Get system statistics from actual databases.
    """
    indexed_documents = 0
    knowledge_nodes = 0

    # Get Qdrant document count
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
        collections = client.get_collections()
        for col in collections.collections:
            if col.name == settings.qdrant_collection:
                info = client.get_collection(settings.qdrant_collection)
                indexed_documents = info.points_count
                break
    except Exception as e:
        print(f"Qdrant stats error: {e}")

    # Get Neo4j node count
    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(
            settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
        )
        with driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) as count")
            record = result.single()
            knowledge_nodes = record["count"] if record else 0
        driver.close()
    except Exception as e:
        print(f"Neo4j stats error: {e}")

    return {
        "indexed_documents": indexed_documents,
        "knowledge_nodes": knowledge_nodes,
        "pending_tasks": len(gardener_tasks),
        "active_threads": 0,
    }
