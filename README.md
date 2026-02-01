# Hybrid Retrieval-Augmented Generation (HRAG) for DevOps

A comprehensive DevOps Incident Response Copilot that leverages a Hybrid RAG architecture, combining Knowledge Graph (Neo4j) for structured relationship retrieval and Vector Database (Qdrant) for semantic search.

## 🚀 Overview

This project implements a "Human-in-the-Loop" architecture for incident management. It assists DevOps engineers by:
- **Ingesting** runbooks, logs, and post-mortems.
- **Extracting** entities and relationships using LLM-based processing.
- **Resolving** conflicts via a "Gardener" interface (Human-in-the-Loop).
- **Reasoning** about incidents using a LangGraph-based agent.
- **Diagnosing** root causes through multi-step reasoning.

## 📂 Project Structure

```
├── hrag-backend/          # FastAPI backend with LangGraph agent
│   ├── app/
│   │   ├── config/        # Domain configuration (YAML schemas)
│   │   ├── graph/         # LangGraph workflow definitions
│   │   ├── services/      # External service integrations (Neo4j, Qdrant, LLM)
│   │   └── api/           # API endpoints
│   └── scripts/           # Seeding and schema scripts
│
├── hrag-frontend/         # Next.js 14 frontend
│   ├── app/               # App Router pages
│   ├── components/        # React components (Copilot, Knowledge, UI)
│   ├── lib/               # Utilities and API client
│   └── hooks/             # Custom React hooks
```

## 🧠 LangGraph Flow

The backend agent follows a structured reasoning flow:

1.  **Input Guard**: Validates user queries and safety.
2.  **Slot Filling**: Extracts key entities (Service, Timestamp, Error Type) from the query.
3.  **Clarification**: Asks the user for missing information if necessary.
4.  **Retrieval**: Fetches context from:
    *   **Neo4j**: For service dependencies and topology.
    *   **Qdrant**: For historical logs and similar past incidents.
5.  **Reasoning**: Analyzes retrieved data to form a hypothesis.
6.  **Response**: Generates a final diagnostic or resolution plan.

## ⚙️ Domain Configuration

The system is designed to be domain-agnostic. While currently configured for **DevOps Incident Response**, the domain logic is defined in YAML files located in `hrag-backend/app/config/`.

To switch domains, one would update:
*   `domain.yaml`: Defines intents, slots, and prompts.
*   `*_schema.py`: Python scripts defining the graph schema (nodes/relationships).

## 🚀 Getting Started

Please refer to the README files in each directory for specific setup instructions:

- [Backend Instructions](./hrag-backend/README.md)
- [Frontend Instructions](./hrag-frontend/README.md)
