from functools import lru_cache
from typing import List

import httpx
from app.core.config import settings
from app.core.logger import logger
from langchain_openai import ChatOpenAI


@lru_cache(maxsize=1)
def get_llm():
    """
    Creates and returns a cached ChatOpenAI instance.
    Uses lru_cache to avoid creating a new instance on every call.
    """
    logger.debug(f"Creating ChatOpenAI instance with model: {settings.llm_model_name}")
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model_name,
        temperature=settings.llm_temperature
        if hasattr(settings, "llm_temperature")
        else 0.7,
    )


# ─── Persistent HTTP client for embedding ───

_embedding_client: httpx.AsyncClient | None = None


def _get_embedding_client() -> httpx.AsyncClient:
    """Get or create a persistent async HTTP client for embeddings."""
    global _embedding_client
    if _embedding_client is None or _embedding_client.is_closed:
        _embedding_client = httpx.AsyncClient(timeout=60.0)
    return _embedding_client


async def close_embedding_client():
    """Close the persistent embedding HTTP client (call on shutdown)."""
    global _embedding_client
    if _embedding_client and not _embedding_client.is_closed:
        await _embedding_client.aclose()
        _embedding_client = None


async def get_embedding(text: str) -> List[float]:
    """
    Generates embeddings for the given text using the configured embedding service.
    Uses a persistent HTTP client to avoid connection overhead.
    """
    headers = {}
    if settings.embedding_api_key:
        headers["Authorization"] = f"Bearer {settings.embedding_api_key}"

    client = _get_embedding_client()
    payload = {
        "input": text,
        "model": settings.embedding_model_name,
    }
    response = await client.post(
        f"{settings.embedding_base_url}/embeddings",
        json=payload,
        headers=headers,
    )
    response.raise_for_status()
    data = response.json()
    return data["data"][0]["embedding"]
