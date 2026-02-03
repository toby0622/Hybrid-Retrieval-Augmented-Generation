from typing import List

import httpx
from langchain_openai import ChatOpenAI
from config import settings
from app.services.auth import token_manager

def get_llm():
    """
    Creates and returns a ChatOpenAI instance.
    Injects J2 Token into Authorization header if enabled.
    """
    default_headers = {"Content-Type": "application/json"}
    
    if settings.token_enabled:
        token = token_manager.get_token()
        if token:
            default_headers["Authorization"] = token

    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model_name,
        temperature=0.7,
        default_headers=default_headers

    )


async def get_embedding(text: str) -> List[float]:
    async with httpx.AsyncClient(timeout=60.0) as client:
        headers = {"Authorization": f"Bearer {settings.embedding_api_key}"}
        if settings.token_enabled:
            token = token_manager.get_token()
            if token:
                headers["Authorization"] = token

        response = await client.post(
            f"{settings.embedding_base_url}/embeddings",
            json={"model": settings.embedding_model_name, "input": text},
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["embedding"]
