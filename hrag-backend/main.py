import uvicorn

from config import settings


def main():
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    HRAG Backend Server                       ║
║          Hybrid Retrieval-Augmented Generation               ║
╠══════════════════════════════════════════════════════════════╣
║  LLM:    {settings.llm_base_url:<48} ║
║  Neo4j:  {settings.neo4j_uri:<48} ║
║  Qdrant: {settings.qdrant_host}:{settings.qdrant_port:<42} ║
╚══════════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "app.api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level="info" if settings.debug else "warning",
    )


if __name__ == "__main__":
    main()
