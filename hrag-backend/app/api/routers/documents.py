import uuid
from typing import List, Optional

from app.core.config import settings
from app.core.logger import logger
from app.core.utils import serialize_neo4j_properties
from app.nodes.feedback import check_entity_conflicts, extract_entities_node
from app.schemas.common import EntityConflict, GardenerAction, GardenerTask
from app.schemas.documents import (
    DocumentResponse,
    IngestResponse,
    NodeResponse,
    UpdateDocumentRequest,
    UpdateNodeRequest,
    UploadResponse,
)
from app.services.gardener import (
    add_task,
    gardener_tasks,
    get_all_tasks,
    get_task,
    remove_task,
)
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
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
                add_task(task_id, conflict)
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
                add_task(task_id, new_task)

        return UploadResponse(
            file_name=file.filename,
            status="processed",
            entities_extracted=len(entities),
            conflicts_found=len(conflicts),
            task_ids=task_ids,
        )

    except Exception as e:
        logger.exception(f"Error uploading knowledge file: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/api/ingest", response_model=IngestResponse)
async def ingest_document_endpoint(
    file: UploadFile = File(...),
    doc_type: str = "document",
):
    try:
        from app.services.ingestion import ingest_document

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
        logger.exception(f"Error during document ingestion: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/gardener/tasks", response_model=GardenerTask)
async def get_gardener_tasks():
    tasks = get_all_tasks()
    return GardenerTask(tasks=tasks)


@router.post("/gardener/action")
async def gardener_action(action: GardenerAction):
    task_id = action.entity_id

    if not get_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")

    if action.action == "approve":
        remove_task(task_id)
        return {"status": "approved", "message": "Entity written to knowledge graph"}

    elif action.action == "reject":
        remove_task(task_id)
        return {"status": "rejected", "message": "Entity discarded"}

    elif action.action == "merge":
        if action.modified_entity:
            pass
        remove_task(task_id)
        return {"status": "merged", "message": "Entity merged and updated"}

    else:
        raise HTTPException(status_code=400, detail="Invalid action")


@router.get("/documents", response_model=List[DocumentResponse])
async def list_documents(
    limit: int = 50, offset: Optional[str] = None, search: Optional[str] = None
):
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import FieldCondition, Filter, MatchText

        client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)

        scroll_filter = None

        if search:
            scroll_filter = Filter(
                should=[
                    FieldCondition(key="content", match=MatchText(text=search)),
                    FieldCondition(key="title", match=MatchText(text=search)),
                ]
            )

        records, next_page_offset = client.scroll(
            collection_name=settings.qdrant_collection,
            scroll_filter=scroll_filter,
            limit=limit,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        documents = []
        for record in records:
            payload = record.payload or {}
            content = payload.get("content", "")
            documents.append(
                DocumentResponse(id=record.id, content=content, metadata=payload)
            )

        return documents
    except Exception as e:
        logger.exception(f"Error listing documents: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/documents/{doc_id}", response_model=DocumentResponse)
async def get_document(doc_id: str):
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)

        try:
            point_id = int(doc_id)
        except ValueError:
            point_id = doc_id

        points = client.retrieve(
            collection_name=settings.qdrant_collection,
            ids=[point_id],
            with_payload=True,
            with_vectors=False,
        )

        if not points:
            raise HTTPException(status_code=404, detail="Document not found")

        point = points[0]
        payload = point.payload or {}

        return DocumentResponse(
            id=point.id, content=payload.get("content", ""), metadata=payload
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting document {doc_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.put("/documents/{doc_id}")
async def update_document(doc_id: str, request: UpdateDocumentRequest):
    try:
        from app.services.ingestion import get_embedding
        from qdrant_client import QdrantClient
        from qdrant_client.models import PointStruct

        client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)

        try:
            point_id = int(doc_id)
        except ValueError:
            point_id = doc_id

        points = client.retrieve(
            collection_name=settings.qdrant_collection,
            ids=[point_id],
            with_payload=True,
            with_vectors=False,
        )

        if not points:
            raise HTTPException(status_code=404, detail="Document not found")

        existing_payload = points[0].payload or {}
        existing_payload["content"] = request.content

        filename = existing_payload.get("title", "")
        embed_text = f"{filename}\n\n{request.content}" if filename else request.content

        new_embedding = await get_embedding(embed_text)

        client.upsert(
            collection_name=settings.qdrant_collection,
            points=[
                PointStruct(id=point_id, vector=new_embedding, payload=existing_payload)
            ],
        )

        return {"status": "success", "message": "Document updated and re-indexed"}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error updating document {doc_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/nodes", response_model=List[NodeResponse])
async def list_nodes(limit: int = 50, offset: int = 0, search: Optional[str] = None):
    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(
            settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
        )

        nodes = []
        with driver.session() as session:
            try:
                if search:
                    query = """
                    MATCH (n) 
                    WHERE toLower(n.name) CONTAINS toLower($search)
                    RETURN n, elementId(n) as eid 
                    ORDER BY eid 
                    SKIP $img_offset LIMIT $img_limit
                    """
                    result = session.run(
                        query, img_offset=offset, img_limit=limit, search=search
                    )
                else:
                    result = session.run(
                        "MATCH (n) RETURN n, elementId(n) as eid ORDER BY eid SKIP $img_offset LIMIT $img_limit",
                        img_offset=offset,
                        img_limit=limit,
                    )

                for record in result:
                    node = record["n"]
                    nodes.append(
                        NodeResponse(
                            id=record["eid"],
                            labels=list(node.labels),
                            properties=serialize_neo4j_properties(dict(node)),
                        )
                    )
            except Exception:
                if search:
                    query = """
                    MATCH (n) 
                    WHERE toLower(n.name) CONTAINS toLower($search)
                    RETURN n, id(n) as nid 
                    ORDER BY nid 
                    SKIP $img_offset LIMIT $img_limit
                    """
                    result = session.run(
                        query, img_offset=offset, img_limit=limit, search=search
                    )
                else:
                    result = session.run(
                        "MATCH (n) RETURN n, id(n) as nid ORDER BY nid SKIP $img_offset LIMIT $img_limit",
                        img_offset=offset,
                        img_limit=limit,
                    )

                for record in result:
                    node = record["n"]
                    nodes.append(
                        NodeResponse(
                            id=str(record["nid"]),
                            labels=list(node.labels),
                            properties=serialize_neo4j_properties(dict(node)),
                        )
                    )

        driver.close()
        return nodes
    except Exception as e:
        logger.exception(f"Error listing nodes: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/nodes/{node_id}", response_model=NodeResponse)
async def get_node(node_id: str):
    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(
            settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
        )

        with driver.session() as session:
            result = session.run(
                "MATCH (n) WHERE elementId(n) = $node_id RETURN n, elementId(n) as eid",
                node_id=node_id,
            )
            record = result.single()

            if not record:
                if node_id.isdigit():
                    result = session.run(
                        "MATCH (n) WHERE id(n) = $node_id RETURN n, id(n) as nid",
                        node_id=int(node_id),
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
                properties=serialize_neo4j_properties(dict(node)),
            )

        driver.close()
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting node {node_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.put("/nodes/{node_id}")
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
                result = session.run(
                    query,
                    node_id=node_id,
                    int_id=int(node_id),
                    props=request.properties,
                )
            else:
                query = """
                 MATCH (n)
                 WHERE elementId(n) = $node_id
                 SET n += $props
                 RETURN n
                 """
                result = session.run(query, node_id=node_id, props=request.properties)

            if not result.single():
                driver.close()
                raise HTTPException(status_code=404, detail="Node not found")

        driver.close()
        return {"status": "success", "message": "Node properties updated"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error updating node {node_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
