# BOR AI Agent Instructions

This document provides guidance for AI agents working on the BOR (Bedrock Orchestration & RAG) codebase.

## Project Overview

BOR is a Python-based system that uses a Retrieval-Augmented Generation (RAG) architecture to answer questions about codebases. It leverages AWS Bedrock for language models, Memgraph for a knowledge graph, and ChromaDB for vector storage.

The system is containerized using Docker. The main components are:
- **REST API**: (`core/restapi/api.py`) The main entry point for interacting with the system. It's a Flask application.
- **Knowledge Base**: (`core/knowledgebase/`) Manages the creation and querying of the knowledge graph and vector embeddings.
- **Data Ingestion**: The system ingests code from local repositories (`core/knowledgebase/code/LocalRepoManager.py`) and text documents, creating a knowledge graph in Memgraph and vector embeddings in ChromaDB.

## Key Components & Data Flow

1.  **Initialization**: `core/knowledgebase/Initializer.py` sets up the knowledge base by scanning repositories and creating graph data and embeddings.
2.  **Query Handling**: `core/knowledgebase/QueryAgents.py` contains agents that handle different types of queries (e.g., `query`, `explain`, `debug`). These agents use prompts from `core/knowledgebase/prompts/` and interact with AWS Bedrock.
3.  **Graph Database**: `core/knowledgebase/MemgraphManager.py` manages the connection to Memgraph and executes Cypher queries. The graph structure represents the codebase's entities and relationships.
4.  **Vector Database**: `core/knowledgebase/notes/Embeddings.py` and `core/knowledgebase/notes/Searcher.py` handle the creation and searching of text embeddings using ChromaDB.
5.  **Authentication**: `core/knowledgebase/AWSAuth.py` handles authentication with AWS Bedrock, supporting multiple methods as defined in `.env.example`.

## Development Workflow

### Setup

The project is designed to run in Docker.

1.  **Configure Environment**: Copy `.env.example` to `.env` and fill in your AWS credentials and other settings.
2.  **Build and Run**: Use `docker-compose up --build` to build and start the services (API, Memgraph, Chroma).
3.  **Run Server Locally**: To run the server outside of Docker for easier debugging, use the `core/run_server.sh` script. This starts the Flask API. Ensure Memgraph and Chroma are accessible.

### Running the Application

-   The main application is a Flask server defined in `core/restapi/api.py`.
-   To run the server locally (without Docker), execute `core/run_server.sh`.
-   The application is containerized. Use `docker-compose up` to run the application and its dependencies (Memgraph, Chroma).

### Testing

There are currently no automated tests in the repository. When adding new features, please consider adding tests.

## Code Conventions

-   The project uses Python with type hints.
-   Configuration is managed through environment variables (see `.env.example`).
-   Prompts for the LLM are stored as separate files in `core/knowledgebase/prompts/`.
-   Follow existing patterns for structuring code. New agents should be added to `core/knowledgebase/QueryAgents.py` and new API endpoints to `core/restapi/api.py`.
