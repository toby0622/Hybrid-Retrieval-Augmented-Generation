from fastapi import APIRouter
from app.schemas.common import HealthResponse
from app.core.config import settings
from app.core.logger import logger

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
async def health_check():
    import asyncio
    
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
            logger.error(f"Health check service error: {e}")
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
            logger.error(f"Neo4j health check failed: {e}")
            return f"error: {str(e)[:50]}"

    def check_qdrant_sync():
        try:
            from qdrant_client import QdrantClient
            client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port, timeout=2.0)
            client.get_collections()
            return "connected"
        except Exception as e:
            logger.error(f"Qdrant health check failed: {e}")
            return f"error: {str(e)[:50]}"

    neo4j_status = await check_service(check_neo4j_sync)
    qdrant_status = await check_service(check_qdrant_sync)

    overall_status = (
        "healthy"
        if all(s == "connected" for s in [neo4j_status, qdrant_status])
        else "degraded"
    )

    return HealthResponse(
        status=overall_status, neo4j=neo4j_status, qdrant=qdrant_status, model_name=settings.llm_model_name
    )

@router.get("/stats")
async def get_stats():
    from app.services.gardener import gardener_tasks
    
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
        logger.error(f"Qdrant stats error: {e}")

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
        logger.error(f"Neo4j stats error: {e}")

    return {
        "indexed_documents": indexed_documents,
        "knowledge_nodes": knowledge_nodes,
        "pending_tasks": len(gardener_tasks),
        "active_threads": 0,
    }
