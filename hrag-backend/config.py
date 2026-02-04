from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model_name: str = ""
    
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model_name: str = ""

    token_url: Optional[str] = None
    llm_j1_token: Optional[str] = None
    embed_j1_token: Optional[str] = None
    token_enabled: bool = False

    neo4j_uri: str = ""
    neo4j_user: str = ""
    neo4j_password: str = ""

    qdrant_host: str = ""
    qdrant_port: int = 6333
    qdrant_collection: str = ""

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False

    active_domain: Optional[str] = None


    # MCP Database Configuration (PostgreSQL)
    mcp_db_host: str = ""
    mcp_db_port: int = 5432
    mcp_db_name: str = ""
    mcp_db_user: str = ""
    mcp_db_password: str = ""
    mcp_enabled: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
