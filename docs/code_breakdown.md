# BOR Codebase Breakdown

This document provides a detailed breakdown of the BOR project structure and workflows.

### Root Directory

*   `.dockerignore`: Specifies files and directories to ignore when building the Docker image.
*   `.env`: (Not present, but created from `.env.example`) Contains environment variables for the application, including AWS credentials and database configurations.
*   `.env.example`: An example file for configuring environment variables.
*   `.git/`: Contains Git repository data.
*   `.github/`: Contains GitHub-specific files, like workflow configurations or issue templates.
    *   `copilot-instructions.md`: Instructions for AI agents working on this codebase.
*   `Dockerfile`: Defines the Docker image for the `bor` service.
*   `LICENSE`: The license for the project.
*   `README.md`: The main README file for the project.
*   `core/`: The main application source code.
*   `docker-compose.yml`: Defines the Docker services, networks, and volumes for the application.
*   `docs_local_install.md`: Documentation for local installation.
*   `requirements.txt`: A list of Python dependencies for the project.
*   `setup.py`: A script for packaging the Python application.

### `core/` Directory

This is the main directory for the application's source code.

*   `__init__.py`: Makes the `core` directory a Python package.
*   `knowledgebase/`: Contains the logic for managing the knowledge base, including data ingestion, querying, and interaction with the LLM.
*   `nuke_docker.sh`: A script to stop and remove all Docker containers, networks, and volumes.
*   `prune_pip.sh`: A script to prune unused pip packages.
*   `restapi/`: Contains the Flask REST API for interacting with the system.
*   `run_memgraph_290.sh`: A script to run Memgraph.
*   `run_server.sh`: A script to run the Flask server locally.

### `core/knowledgebase/` Directory

This directory is the heart of the RAG system.

*   `__init__.py`: Makes the `knowledgebase` directory a Python package.
*   `AWSAuth.py`: Handles authentication with AWS Bedrock.
*   `CypherQueryHandler.py`: Handles the generation and execution of Cypher queries against Memgraph.
*   `Initializer.py`: Initializes the knowledge base by populating it with data from a specified source (previously mock data, now an Obsidian vault).
*   `MemgraphManager.py`: Manages the connection to and interaction with the Memgraph database.
*   `QueryAgents.py`: Contains different "agents" that handle specific types of queries (e.g., `explain`, `debug`).
*   `TextAnalizer.py`: Analyzes text to extract entities and relationships for building the knowledge graph.
*   `Utils.py`: Contains utility functions.
*   `code/`: Manages code repositories as a source of knowledge.
*   `constants.py`: Contains constant values used throughout the knowledge base.
*   `notes/`: Manages notes (like from an Obsidian vault) as a source of knowledge.
*   `prompts/`: Contains prompt templates for interacting with the LLM.

### `core/knowledgebase/code/` Directory

*   `__init__.py`: Makes the `code` directory a Python package.
*   `APIRepoManager.py`: Manages repositories from APIs.
*   `LocalRepoManager.py`: Manages local code repositories.
*   `languages.yml`: A YAML file defining supported programming languages.

### `core/knowledgebase/notes/` Directory

*   `__init__.py`: Makes the `notes` directory a Python package.
*   `CollectionManager.py`: Manages collections of notes in the Chroma vector database.
*   `Embeddings.py`: Handles the creation of text embeddings using a Bedrock model.
*   `Searcher.py`: Searches for similar notes in the vector database.
*   `VaultManager.py`: Manages the ingestion of notes from an Obsidian vault.

### `core/knowledgebase/prompts/` Directory

This directory contains the prompt templates sent to the LLM. There are two types of prompts for each query type: a `prompt_*` which is the user-facing prompt, and a `system_message_*` which provides context and instructions to the LLM.

### `core/restapi/` Directory

*   `__init__.py`: Makes the `restapi` directory a Python package.
*   `api.py`: Defines the Flask REST API endpoints for interacting with the BOR system.

## Workflows

### 1. Data Ingestion Workflow

1.  The `Initializer.py` script is run.
2.  It connects to Memgraph and ChromaDB and clears any existing data.
3.  It reads the `OBSIDIAN_VAULT_PATH` environment variable to find the location of the knowledge base.
4.  The `VaultManager` is used to recursively scan the vault directory for markdown files.
5.  For each file:
    *   The `TextAnalizer` is used to convert the text into Cypher `CREATE` queries to build the knowledge graph in Memgraph.
    *   The `CollectionManager` adds the file to a ChromaDB collection.
    *   Embeddings are created for the file content using `Embeddings.py` and stored in ChromaDB.

### 2. Query Workflow

1.  A user sends a request to one of the endpoints in `core/restapi/api.py` (e.g., `/query`, `/explain`).
2.  The API calls the appropriate agent in `QueryAgents.py`.
3.  The agent performs a similarity search against the ChromaDB vector store via `Searcher.py` to find relevant notes/documents.
4.  The agent uses `CypherQueryHandler.py` to query the Memgraph knowledge graph for relevant entities and relationships.
5.  The agent combines the user's query, the retrieved documents, and the graph data into a prompt using the templates from the `core/knowledgebase/prompts/` directory.
6.  The prompt is sent to the AWS Bedrock language model via `AWSAuth.py`.
7.  The LLM's response is returned to the user through the API.
