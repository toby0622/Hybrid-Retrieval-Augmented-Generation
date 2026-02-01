# HRAG Backend

The backend for the Hybrid RAG DevOps Copilot, built with FastAPI, LangGraph, Neo4j, and Qdrant.

## 🛠️ Prerequisites

- **Python 3.11+**
- **Neo4j Database** (Local or Aura)
- **Qdrant Instance** (Local or Cloud)
- **Google Gemini API Key** (or other LLM provider)

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
    GOOGLE_API_KEY=your_key_here
    NEO4J_URI=bolt://localhost:7687
    NEO4J_USERNAME=neo4j
    NEO4J_PASSWORD=password
    QDRANT_URL=http://localhost:6333
    QDRANT_API_KEY=your_key_here
    ```

## 🗄️ Database Seeding

Before running the app, seed the databases with the DevOps schema and sample data:

```bash
# Seed Graph Data (Neo4j)
python scripts/seed_neo4j_devops.py

# Seed Vector Data (Qdrant)
python scripts/seed_qdrant_devops.py
```

## 🚀 Running the Server

Start the FastAPI server:

```bash
python main.py
```

The API will be available at `http://localhost:8000`.
API Documentation (Swagger UI) is available at `http://localhost:8000/docs`.
