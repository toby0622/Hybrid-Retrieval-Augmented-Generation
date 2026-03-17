from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model_name: str = ""
    llm_temperature: float = 0.7

    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model_name: str = ""
    embedding_dim: int = 768

    neo4j_uri: str = ""
    neo4j_user: str = ""
    neo4j_password: str = ""

    qdrant_host: str = ""
    qdrant_port: int = 6333
    qdrant_collection: str = ""

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False

    skills_dir: str = "skills"

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    mcp_db_host: str = ""
    mcp_db_port: int = 5432
    mcp_db_name: str = ""
    mcp_db_user: str = ""
    mcp_db_password: str = ""
    mcp_enabled: bool = False

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse comma-separated CORS origins into a list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
