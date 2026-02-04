# HRAG Backend

The backend for the Hybrid RAG DevOps Copilot, built with FastAPI, LangGraph, Neo4j, and Qdrant. Now featuring **MCP (Model Context Protocol)** for real-time data and a **Dynamic Schema Registry**.

## 🛠️ Prerequisites

- **Python 3.11+**
- **Neo4j Database** (Local or Aura)
- **Qdrant Instance** (Local or Cloud)
- **Google Gemini API Key** (or other LLM provider)
- **PostgreSQL Database** (for MCP Real-time data simulation)

## 📦 Installation

1.  Navigate to the backend directory:
    ```bash
    cd hrag-backend
    ```

2.  Create and activate a virtual environment:
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```

3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

4.  Set up environment variables:
    Create a `.env` file (copy from `.env.example`) and populate it:
    ```env
    # LLM Configuration (LM Studio local server)
    LLM_BASE_URL=http://localhost:8192/v1
    LLM_API_KEY=lm-studio
    LLM_MODEL_NAME=google/gemma-3-27b
    EMBEDDING_MODEL_NAME=text-embedding-embeddinggemma-300m

    # Neo4j Configuration
    NEO4J_URI=bolt://localhost:7687
    NEO4J_USER=neo4j
    NEO4J_PASSWORD=password

    # Qdrant Configuration
    QDRANT_HOST=localhost
    QDRANT_PORT=6333
    QDRANT_COLLECTION=hrag_documents

    # API Configuration
    API_HOST=0.0.0.0
    API_PORT=8000
    DEBUG=true

    # MCP Configuration (Real-time Data)
    MCP_ENABLED=true
    MCP_DB_HOST=localhost
    MCP_DB_PORT=5432
    MCP_DB_NAME=devops_metrics
    MCP_DB_USER=postgres
    MCP_DB_PASSWORD=password
    ```

## 🗄️ Database Seeding

Before running the app, seed the databases with the DevOps schema and sample data:

```bash
# Seed Graph Data (Neo4j)
python scripts/seed_neo4j_devops.py

# Seed Vector Data (Qdrant)
python scripts/seed_qdrant_devops.py

# Seed MCP Data (PostgreSQL/SQLAlchemy)
python scripts/seed_mcp_data.py
```

## 🚀 Running the Server

Start the FastAPI server:

```bash
python main.py
```

The API will be available at `http://localhost:8000`.
API Documentation (Swagger UI) is available at `http://localhost:8000/docs`.

## 🔌 API Endpoints

The backend exposes the following main routers (see `app/api/routers`):

- **`/chat`**: Main interaction endpoint for the chatbot.
- **`/documents`**: Endpoints for uploading, listing, and deleting knowledge base documents.
- **`/health`**: System health checks for database connections (Neo4j, Qdrant).

