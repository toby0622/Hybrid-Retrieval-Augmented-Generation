# HRAG Backend

The backend for the Hybrid RAG system, built with FastAPI, LangGraph, Neo4j, and Qdrant. Featuring **MCP (Model Context Protocol)** for real-time data and a **Dynamic Schema Registry**.

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
    # LLM Configuration
    LLM_BASE_URL="your_llm_api_base_url_here"
    LLM_API_KEY="your_llm_api_key_here"
    LLM_MODEL_NAME="your_llm_model_name_here"
    EMBEDDING_MODEL_NAME="your_embedding_model_name_here"

    # ... see .env.example for all variables
    ```

## 🗄️ Database Seeding

To seed your database, you should create a domain configuration in `config/domains/` and a corresponding schema in `scripts/`. Use the provided templates as a guide:

- `config/domains/template.yaml.example`
- `scripts/template_schema.py.example`

After creating your own seeding scripts based on these templates, you can run them:

```bash
# Example seeding command
python scripts/seed_your_domain.py
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

