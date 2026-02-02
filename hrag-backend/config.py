from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    llm_base_url: str = "http://localhost:8192/v1"
    llm_api_key: str = "lm-studio"
    llm_model_name: str = "google/gemma-3-27b"
    embedding_model_name: str = "text-embedding-embeddinggemma-300m"

    token_url: Optional[str] = None
    j1_token: Optional[str] = None
    token_enabled: bool = False

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "hrag_documents"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = True

    active_domain: str = "email"
    scripts_path: str = "scripts"
    domains_path: str = "config/domains"

    # MCP Database Configuration (PostgreSQL)
    mcp_db_host: str = "localhost"
    mcp_db_port: int = 5432
    mcp_db_name: str = "hrag_mcp"
    mcp_db_user: str = "postgres"
    mcp_db_password: str = "postgres"
    mcp_enabled: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
