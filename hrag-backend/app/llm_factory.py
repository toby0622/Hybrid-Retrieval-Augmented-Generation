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
        # This might block if token/exchange is needed
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
