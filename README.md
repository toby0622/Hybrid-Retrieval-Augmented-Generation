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
├── hrag-backend/              # FastAPI backend
│   ├── app/
│   │   ├── api/               # API Router Endpoints
│   │   ├── core/              # Core Config & Logging
│   │   ├── nodes/             # LangGraph Nodes
│   │   │   ├── input_guard.py # Safety & Validation
│   │   │   ├── slot_filling.py# Entity Extraction
│   │   │   ├── retrieval.py   # Hybrid Retrieval (Neo4j + Qdrant)
│   │   │   ├── reasoning.py   # Chain-of-Thought Logic
│   │   │   ├── mcp_tools.py   # MCP Tool Definitions
│   │   │   ├── response.py    # Final Answer Generation
│   │   │   └── feedback.py    # Human-in-the-Loop Handling
│   │   ├── schemas/           # Pydantic Models (Chat, Documents)
│   │   ├── services/          # Business Logic
│   │   │   ├── ingestion.py   # Data Ingestion Service
│   │   │   ├── mcp.py         # MCP Client Service
│   │   │   └── auth.py        # Authentication Service
│   │   ├── graph.py           # Main LangGraph Workflow
│   │   ├── state.py           # State Definition
│   │   ├── schema_registry.py # Dynamic Domain Schema Registry
│   │   └── domain_config.py   # Domain Specific Config Loader
│   ├── config/                # YAML Configuration Files
│   ├── scripts/               # Database Seeding Scripts
│   └── main.py                # Server Entry Point
│
├── hrag-frontend/             # Next.js 16 frontend
│   ├── app/                   # App Router (Pages & Layouts)
│   ├── components/            # React Components
│   │   ├── copilot/           # Chat Interface & Reasoning UI
│   │   ├── knowledge/         # Knowledge Base Management
│   │   ├── layout/            # Layout Components
│   │   └── ui/                # Shared UI Components
│   ├── lib/                   # Utilities & API Clients
│   ├── hooks/                 # Custom React Hooks
│   └── types/                 # TypeScript Definitions
```

## 🧠 LangGraph Flow

The backend agent follows a structured reasoning flow:

1.  **Input Guard**: Validates user queries and safety.
2.  **Slot Filling**: Extracts key entities (Service, Timestamp, Error Type) from the query.
3.  **Clarification**: Asks the user for missing information if necessary.
4.  **Retrieval**: Fetches context from:
    *   **Neo4j**: For service dependencies and topology.
    *   **Qdrant**: For historical logs and similar past incidents.
5.  **Real-time Data (MCP)**: Queries live SQL databases for metrics, logs, and health status.
6.  **Reasoning**: Analyzes retrieved data to form a hypothesis.
7.  **Response**: Generates a final diagnostic or resolution plan.

## ⚙️ Domain Configuration

The system is designed to be domain-agnostic. While currently configured for **DevOps Incident Response**, the domain logic is defined in YAML files located in `hrag-backend/app/config/`.

To switch domains, one would update:
*   `domain.yaml`: Defines intents, slots, and prompts.
*   `*_schema.py`: Python scripts defining the graph schema (nodes/relationships).

## 🚀 Getting Started

Please refer to the README files in each directory for specific setup instructions:

- [Backend Instructions](./hrag-backend/README.md)
- [Frontend Instructions](./hrag-frontend/README.md)
