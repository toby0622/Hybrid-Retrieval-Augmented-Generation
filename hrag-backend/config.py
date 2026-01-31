"""
HRAG Backend Configuration
Loads environment variables and provides typed settings
"""

from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # LLM Configuration (LM Studio compatible)
    llm_base_url: str = "http://localhost:8192/v1"
    llm_api_key: str = "lm-studio"
    llm_model_name: str = "google/gemma-3-27b"
    embedding_model_name: str = "text-embedding-embeddinggemma-300m"

    # Neo4j Configuration
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"

    # Qdrant Configuration
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "hrag_documents"

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = True

    # Domain Configuration
    active_domain: str = "email"  # Default domain (can be: email, devops, etc.)
    scripts_path: str = "scripts"  # Path to *_schema.py files
    domains_path: str = "config/domains"  # Path to *.yaml domain configs

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
