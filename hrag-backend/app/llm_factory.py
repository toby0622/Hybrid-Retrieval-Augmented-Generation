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
        token = token_manager.get_token(token_type="llm")
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
            token = token_manager.get_token(token_type="embedding")
            if token:
                headers["Authorization"] = token

        if settings.token_enabled:
            payload = {
                "text": text,
                "model": settings.embedding_model_name,
                "encoding-format": "float"
            }
            response = await client.post(
                f"{settings.embedding_base_url}",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            return data["returnData"][0]["embeddings"]
        else:
            payload = {
                "input": text,
                "model": settings.embedding_model_name,
            }
            response = await client.post(
                f"{settings.embedding_base_url}/embeddings",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]
