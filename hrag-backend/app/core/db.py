from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from app.core.config import settings

_neo4j_driver = None
_qdrant_client = None


def get_neo4j_driver():
    """Get or create a shared sync Neo4j driver."""
    global _neo4j_driver
    if _neo4j_driver is None:
        _neo4j_driver = GraphDatabase.driver(
            settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
        )
    return _neo4j_driver


def get_qdrant_client():
    """Get or create a shared Qdrant client."""
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(
            host=settings.qdrant_host, port=settings.qdrant_port
        )
    return _qdrant_client


def close_db_clients():
    """Cleanup DB clients on shutdown."""
    global _neo4j_driver, _qdrant_client
    if _neo4j_driver:
        _neo4j_driver.close()
        _neo4j_driver = None
    _qdrant_client = None
