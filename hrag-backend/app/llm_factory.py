from typing import List

import httpx
from app.core.config import settings
from langchain_openai import ChatOpenAI


def get_llm():
    """
    Creates and returns a ChatOpenAI instance.
    """
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model_name,
        temperature=0.7,
    )


async def get_embedding(text: str) -> List[float]:
    async with httpx.AsyncClient(timeout=60.0) as client:
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
