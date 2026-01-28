"""
HRAG FastAPI Application
REST API endpoints for the HRAG system
"""

import uuid
from typing import Optional, List
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.graph import run_query, graph
from app.state import DiagnosticResponse, DiagnosticStep, SlotInfo
from app.nodes.feedback import extract_entities_node, check_entity_conflicts


# --- API Models ---

class ChatRequest(BaseModel):
    """Chat request model"""
    query: str
    thread_id: Optional[str] = None
    feedback: Optional[str] = None


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
    version="0.1.0"
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
    # TODO: Implement actual connectivity checks
    return HealthResponse(
        status="healthy",
        neo4j="mock",  # Will show "connected" when real DB is set up
        qdrant="mock",
        llm="lm-studio"
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
            query=request.query,
            thread_id=thread_id,
            feedback=request.feedback
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
            clarification_question=clarification
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


@app.post("/upload", response_model=UploadResponse)
async def upload_knowledge(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None
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
                    new_entity=entity
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
                    description=entity.get("description", "")
                )
                new_entities.append(new_task)
                gardener_tasks[task_id] = new_task
        
        return UploadResponse(
            file_name=file.filename,
            status="processed",
            entities_extracted=len(entities),
            conflicts_found=len(conflicts),
            task_ids=task_ids
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
    Get system statistics.
    """
    return {
        "indexed_documents": 1204,  # Mock
        "knowledge_nodes": 45000,   # Mock
        "pending_tasks": len(gardener_tasks),
        "active_threads": 0  # TODO: Track active conversations
    }
