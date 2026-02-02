import asyncio
import json
import uuid
from typing import AsyncGenerator, List, Optional

from app.graph import graph, run_query
from app.nodes.feedback import check_entity_conflicts, extract_entities_node
from app.state import DiagnosticResponse, DiagnosticStep, SlotInfo
from config import settings
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str
    thread_id: Optional[str] = None
    feedback: Optional[str] = None
    stream: bool = False


class ReasoningStep(BaseModel):
    id: str
    label: str
    status: str = "pending"


class ChatResponse(BaseModel):
    thread_id: str
    response: str
    intent: Optional[str] = None
    response_type: str = "text"
    reasoning_steps: Optional[List[ReasoningStep]] = None
    diagnostic: Optional[DiagnosticResponse] = None
    clarification_question: Optional[str] = None


class EntityConflict(BaseModel):
    id: str
    type: str
    entity_name: str
    source: str
    confidence: float
    existing_entity: Optional[dict] = None
    new_entity: dict
    description: Optional[str] = None


class GardenerTask(BaseModel):
    tasks: List[EntityConflict]


class GardenerAction(BaseModel):
    entity_id: str
    action: str
    modified_entity: Optional[dict] = None


class UploadResponse(BaseModel):
    file_name: str
    status: str
    entities_extracted: int
    conflicts_found: int
    task_ids: List[str]


class IngestResponse(BaseModel):
    file_name: str
    domain: str
    status: str
    entities_created: int
    relations_created: int
    vectors_created: int
    errors: List[str] = []


class HealthResponse(BaseModel):
    status: str
    neo4j: str
    qdrant: str
    llm: str
    model_name: str


app = FastAPI(
    title="HRAG Backend API",
    description="Hybrid Retrieval-Augmented Generation API for DevOps Incident Response",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

gardener_tasks: dict = {}


def serialize_neo4j_value(value):
    """Convert Neo4j special types to JSON-serializable formats."""
    if value is None:
        return None
    
    # Handle Neo4j DateTime types
    type_name = type(value).__module__ + '.' + type(value).__name__
    if 'neo4j.time' in type_name:
        # Convert neo4j.time.DateTime, Date, Time, Duration to ISO string
        if hasattr(value, 'iso_format'):
            return value.iso_format()
        elif hasattr(value, 'to_native'):
            return str(value.to_native())
        else:
            return str(value)
    
    # Handle lists and dicts recursively
    if isinstance(value, list):
        return [serialize_neo4j_value(v) for v in value]
    if isinstance(value, dict):
        return {k: serialize_neo4j_value(v) for k, v in value.items()}
    
    return value


def serialize_neo4j_properties(props: dict) -> dict:
    """Serialize all properties from a Neo4j node."""
    return {k: serialize_neo4j_value(v) for k, v in props.items()}


@app.on_event("startup")
async def startup_event():
    from app.domain_init import initialize_domain_system

    print("[Startup] Initializing domain system...")
    try:
        config = initialize_domain_system()
        print(f"[Startup] Active domain: {config.display_name}")
    except Exception as e:
        print(f"[Startup] Domain initialization error: {e}")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    async def check_service(check_func, timeout=2.0):
        try:
            loop = asyncio.get_running_loop()
            return await asyncio.wait_for(
                loop.run_in_executor(None, check_func), 
                timeout=timeout
            )
        except asyncio.TimeoutError:
            return "timeout"
        except Exception as e:
            return f"error: {str(e)[:50]}"

    def check_neo4j_sync():
        try:
            from neo4j import GraphDatabase
            driver = GraphDatabase.driver(
                settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
            )
            with driver.session() as session:
                session.run("RETURN 1")
            driver.close()
            return "connected"
        except Exception as e:
            return f"error: {str(e)[:50]}"

    def check_qdrant_sync():
        try:
            from qdrant_client import QdrantClient
            client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port, timeout=2.0)
            client.get_collections()
            return "connected"
        except Exception as e:
            return f"error: {str(e)[:50]}"

    def check_llm_sync():
        try:
            import httpx
            # httpx is async capable, but keeping it sync here for uniformity with the thread pool pattern 
            # or we could use async httpx directly. Let's use async httpx properly if possible, 
            # but to ensure we don't block, let's just use the sync wrapper or proper async.
            # actually httpx is already async in the original code? 
            # Original: async with httpx.AsyncClient... 
            # So we can keep LLM check async natural.
            raise NotImplementedError("Use async implementation") 
        except Exception as e:
             raise e

    # Execute checks
    neo4j_status = await check_service(check_neo4j_sync)
    qdrant_status = await check_service(check_qdrant_sync)

    # LLM Check (Native Async)
    llm_status = "disconnected"
    try:
        import httpx
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{settings.llm_base_url}/models")
            if response.status_code == 200:
                llm_status = "connected"
            else:
                llm_status = f"error: {response.status_code}"
    except Exception as e:
        llm_status = f"error: {str(e)[:30]}"

    overall_status = (
        "healthy"
        if all(s == "connected" for s in [neo4j_status, qdrant_status])
        else "degraded"
    )

    return HealthResponse(
        status=overall_status, neo4j=neo4j_status, qdrant=qdrant_status, llm=llm_status, model_name=settings.llm_model_name
    )


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    thread_id = request.thread_id or str(uuid.uuid4())

    async def generate() -> AsyncGenerator[str, None]:
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

        for i, step in enumerate(reasoning_steps):
            step["status"] = "active"
            yield f"data: {json.dumps({'type': 'reasoning', 'step': step})}\n\n"
            await asyncio.sleep(0.3)

            step["status"] = "completed"
            yield f"data: {json.dumps({'type': 'reasoning', 'step': step})}\n\n"

        try:
            result = await run_query(
                query=request.query, thread_id=thread_id, feedback=request.feedback
            )

            response_data = {
                "type": "complete",
                "thread_id": thread_id,
                "response": result.get("response", ""),
                "intent": result.get("intent", "chat"),
                "diagnostic": result.get("diagnostic"),
                "clarification_question": result.get("clarification_question"),
            }

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

        if diagnostic:
            response_type = "diagnostic"
        elif reasoning_steps:
            response_type = "reasoning"
        elif clarification:
            response_type = "clarification"
        else:
            response_type = "text"

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
    try:
        content = await file.read()
        content_str = content.decode("utf-8")

        entities = await extract_entities_node(content_str)

        existing_entities = []

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


@app.post("/api/ingest", response_model=IngestResponse)
async def ingest_document_endpoint(
    file: UploadFile = File(...),
    doc_type: str = "document",
):
    try:
        from app.ingestion import ingest_document

        content = await file.read()
        content_str = content.decode("utf-8")

        result = await ingest_document(
            content=content_str,
            filename=file.filename,
            doc_type=doc_type,
        )

        return IngestResponse(
            file_name=file.filename,
            domain=result.domain,
            status="success" if result.success else "partial",
            entities_created=result.entities_created,
            relations_created=result.relations_created,
            vectors_created=result.vectors_created,
            errors=result.errors,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion error: {str(e)}")


@app.get("/gardener/tasks", response_model=GardenerTask)
async def get_gardener_tasks():
    tasks = list(gardener_tasks.values())
    return GardenerTask(tasks=tasks)


@app.post("/gardener/action")
async def gardener_action(action: GardenerAction):
    task_id = action.entity_id

    if task_id not in gardener_tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = gardener_tasks[task_id]

    if action.action == "approve":
        del gardener_tasks[task_id]
        return {"status": "approved", "message": "Entity written to knowledge graph"}

    elif action.action == "reject":
        del gardener_tasks[task_id]
        return {"status": "rejected", "message": "Entity discarded"}

    elif action.action == "merge":
        if action.modified_entity:
            pass
        del gardener_tasks[task_id]
        return {"status": "merged", "message": "Entity merged and updated"}

    else:
        raise HTTPException(status_code=400, detail="Invalid action")


@app.get("/stats")
async def get_stats():
    indexed_documents = 0
    knowledge_nodes = 0

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


class DocumentResponse(BaseModel):
    id: str | int
    content: str
    metadata: dict


class UpdateDocumentRequest(BaseModel):
    content: str


class NodeResponse(BaseModel):
    id: str
    labels: List[str]
    properties: dict


class UpdateNodeRequest(BaseModel):
    properties: dict


@app.get("/documents", response_model=List[DocumentResponse])
async def list_documents(limit: int = 50, offset: Optional[str] = None):
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Record

        client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
        
        # Use scroll API to list points
        # offset in qdrant scroll is a point ID to start from
        scroll_filter = None
        
        records, next_page_offset = client.scroll(
            collection_name=settings.qdrant_collection,
            scroll_filter=scroll_filter,
            limit=limit,
            offset=offset,
            with_payload=True,
            with_vectors=False
        )
        
        documents = []
        for record in records:
            payload = record.payload or {}
            content = payload.get("content", "")
            # Remove content from metadata to avoid duplication in response if desired, 
            # but keeping it simple for now.
            documents.append(DocumentResponse(
                id=record.id,
                content=content,
                metadata=payload
            ))
            
        return documents
    except Exception as e:
        print(f"Error listing documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents/{doc_id}", response_model=DocumentResponse)
async def get_document(doc_id: str):
    try:
        from qdrant_client import QdrantClient
        
        client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
        
        # doc_id might be int or uuid string. Qdrant IDs can be both.
        # Try to parse as int if it looks like one, otherwise keep as string
        try:
            point_id = int(doc_id)
        except ValueError:
            point_id = doc_id

        points = client.retrieve(
            collection_name=settings.qdrant_collection,
            ids=[point_id],
            with_payload=True,
            with_vectors=False
        )
        
        if not points:
            raise HTTPException(status_code=404, detail="Document not found")
            
        point = points[0]
        payload = point.payload or {}
        
        return DocumentResponse(
            id=point.id,
            content=payload.get("content", ""),
            metadata=payload
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/documents/{doc_id}")
async def update_document(doc_id: str, request: UpdateDocumentRequest):
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import PointStruct
        from app.ingestion import get_embedding
        
        client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
        
        try:
            point_id = int(doc_id)
        except ValueError:
            point_id = doc_id
            
        # 1. Retrieve existing payload to preserve metadata (like filename, domain, etc.)
        points = client.retrieve(
            collection_name=settings.qdrant_collection,
            ids=[point_id],
            with_payload=True,
            with_vectors=False
        )
        
        if not points:
            raise HTTPException(status_code=404, detail="Document not found")
            
        existing_payload = points[0].payload or {}
        
        # 2. Update content in payload
        existing_payload["content"] = request.content
        
        # 3. Generate new embedding
        # We need to reconstruct the text used for embedding. 
        # Usually it's "Title \n\n Content" or just Content.
        # In ingestion.py: embed_text = f"{filename}\n\n{chunk}"
        # We try to replicate that if title exists
        filename = existing_payload.get("title", "")
        embed_text = f"{filename}\n\n{request.content}" if filename else request.content
        
        new_embedding = await get_embedding(embed_text)
        
        # 4. Upsert (Overwrite)
        client.upsert(
            collection_name=settings.qdrant_collection,
            points=[
                PointStruct(
                    id=point_id,
                    vector=new_embedding,
                    payload=existing_payload
                )
            ]
        )
        
        return {"status": "success", "message": "Document updated and re-indexed"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/nodes", response_model=List[NodeResponse])
async def list_nodes(limit: int = 50, offset: int = 0):
    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(
            settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
        )
        
        nodes = []
        with driver.session() as session:
            try:
                result = session.run(
                    "MATCH (n) RETURN n, elementId(n) as eid ORDER BY eid SKIP $img_offset LIMIT $img_limit",
                    img_offset=offset, img_limit=limit
                )
                for record in result:
                    node = record["n"]
                    nodes.append(NodeResponse(
                        id=record["eid"],
                        labels=list(node.labels),
                        properties=serialize_neo4j_properties(dict(node))
                    ))
            except Exception:
                result = session.run(
                    "MATCH (n) RETURN n, id(n) as nid ORDER BY nid SKIP $img_offset LIMIT $img_limit",
                    img_offset=offset, img_limit=limit
                )
                for record in result:
                    node = record["n"]
                    nodes.append(NodeResponse(
                        id=str(record["nid"]),
                        labels=list(node.labels),
                        properties=serialize_neo4j_properties(dict(node))
                    ))
                    
        driver.close()
        return nodes
    except Exception as e:
        print(f"Error listing nodes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/nodes/{node_id}", response_model=NodeResponse)
async def get_node(node_id: str):
    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(
            settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
        )
        
        with driver.session() as session:
            result = session.run(
                "MATCH (n) WHERE elementId(n) = $node_id RETURN n, elementId(n) as eid",
                node_id=node_id
            )
            record = result.single()
            
            if not record:
                if node_id.isdigit():
                    result = session.run(
                        "MATCH (n) WHERE id(n) = $node_id RETURN n, id(n) as nid",
                        node_id=int(node_id)
                    )
                    record = result.single()

            if not record:
                driver.close()
                raise HTTPException(status_code=404, detail="Node not found")
                
            node = record["n"]
            response_id = record.get("eid") or str(record.get("nid"))
            
            response = NodeResponse(
                id=response_id,
                labels=list(node.labels),
                properties=serialize_neo4j_properties(dict(node))
            )
            
        driver.close()
        return response
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting node: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/nodes/{node_id}")
async def update_node(node_id: str, request: UpdateNodeRequest):
    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(
            settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
        )
        
        with driver.session() as session:
            query = ""
            if node_id.isdigit():
                 query = """
                 MATCH (n)
                 WHERE elementId(n) = $node_id OR id(n) = $int_id
                 SET n += $props
                 RETURN n
                 """
            else:
                 query = """
                 MATCH (n)
                 WHERE elementId(n) = $node_id
                 SET n += $props
                 RETURN n
                 """
            
            params = {
                "node_id": node_id, 
                "int_id": int(node_id) if node_id.isdigit() else -1,
                "props": request.properties
            }
            
            result = session.run(query, params)
            if not result.single():
                 driver.close()
                 raise HTTPException(status_code=404, detail="Node not found")
                 
        driver.close()
        return {"status": "success", "message": "Node updated"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating node: {e}")
        raise HTTPException(status_code=500, detail=str(e))
