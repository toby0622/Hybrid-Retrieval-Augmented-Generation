from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import chat, documents, health
from app.core.config import settings
from app.core.logger import logger


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
        from app.core.db import close_db_clients
        from app.llm_factory import close_embedding_client

        close_db_clients()
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

# Optional basic API key for sensitive endpoints
API_KEY = os.getenv("API_KEY", "hrag-dev-key")


@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    # Allow health check and OPTIONS requests
    if request.url.path == "/api/health" or request.method == "OPTIONS":
        return await call_next(request)

    # Protect these endpoints
    protected_prefixes = ["/upload", "/api/ingest", "/nodes", "/documents", "/gardener"]
    is_protected = any(request.url.path.startswith(prefix) for prefix in protected_prefixes)
    
    if is_protected:
        auth_header = request.headers.get("Authorization")
        if not auth_header or auth_header != f"Bearer {API_KEY}":
            return JSONResponse(status_code=401, content={"detail": "Unauthorized / Invalid API Key"})

    return await call_next(request)

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
