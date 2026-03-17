from contextlib import asynccontextmanager

from app.api.routers import chat, documents, health
from app.core.config import settings
from app.core.logger import logger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    from app.skill_registry import SkillRegistry

    logger.info("Initializing skill system...")
    try:
        config = SkillRegistry.initialize()
        logger.info(f"Active skill: {config.display_name}")
    except Exception as e:
        logger.exception(f"Skill initialization error: {e}")
    yield
    # Shutdown — cleanup all connections
    logger.info("Shutting down, cleaning up resources...")
    try:
        from app.api.routers.documents import close_document_clients
        from app.llm_factory import close_embedding_client
        from app.nodes.retrieval import Neo4jClient, QdrantClientWrapper

        await Neo4jClient.close()
        QdrantClientWrapper._client = None
        close_document_clients()
        await close_embedding_client()
        logger.info("All resources cleaned up.")
    except Exception as e:
        logger.warning(f"Cleanup error (non-fatal): {e}")


app = FastAPI(
    title="HRAG Backend API",
    description="Hybrid Retrieval-Augmented Generation API for DevOps Incident Response",
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(documents.router)
app.include_router(health.router)
