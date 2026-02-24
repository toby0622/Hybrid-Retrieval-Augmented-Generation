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
    # Shutdown (cleanup resources if needed)


app = FastAPI(
    title="HRAG Backend API",
    description="Hybrid Retrieval-Augmented Generation API for DevOps Incident Response",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(documents.router)
app.include_router(health.router)
