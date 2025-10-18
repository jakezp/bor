[![python](https://img.shields.io/badge/python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![fastapi](https://img.shields.io/badge/fastapi-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![docker](https://img.shields.io/badge/docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)

# BOR — Bedrock Orchestration & RAG backend

BOR is a FastAPI backend that builds a knowledge graph (Memgraph) and vector index (ChromaDB) over your notes and code, then uses AWS Bedrock models for embeddings and analysis. It’s designed to power frontends (e.g., an Obsidian plugin) with reliable retrieval and developer-friendly JSON APIs.

Forked from: https://github.com/memgraph/bor  
This repository: https://github.com/jakezp/bor

What you get:
- Incremental Obsidian vault ingestion (graph + vectors)
- GitHub code repo structure ingestion (Repo/Dir/File graph)
- Stable vector search using pure-Cypher cosine similarity
- JSON-first Text Analyzer endpoints (explain, style, debug, questions)
- Debug endpoints and smoke tests for confidence
- Auto-generated Markdown API reference from OpenAPI

## Table of contents
- Why BOR?
- Features
- Architecture overview
- Installation
    - Docker (recommended)
    - Local development
- Configuration
- Running the server
- API and documentation
- Usage examples (curl)
- Obsidian plugin notes
- Operations and smoke tests
- Contributing
- Acknowledgements & origin
- License

## Why BOR?
We want a robust backend that:
- Understands both structure and semantics (graph + vectors)
- Integrates cleanly with AWS Bedrock for embeddings and LLM tasks
- Exposes simple, JSON-first endpoints suitable for plugins and apps
- Is observable and testable from day one

## Features
- Storage:
    - Memgraph: graph of Repo/Dir/File, sentence nodes, and relationships
    - ChromaDB: sentence vectors (Bedrock embeddings, caching)
- Ingestion:
    - Notes (Obsidian vault): incremental ingest with per-repo state files
    - Code (GitHub): directory tree via contents API (stable repo_path: github://owner/repo)
- Vector search:
    - Pure-Cypher cosine against per-request :Temp nodes (excludes :Temp from corpus)
    - Bounds and input validation on top_k
- Text Analyzer (JSON-first):
    - Endpoints for explain/debug/style/questions with 6,000-char cap and markdown fallback
- Debug and ops:
    - Health, chroma, graph overview, and vector score endpoints
- Tooling:
    - Docker Compose orchestration
    - Smoke tests and VS Code tasks
    - OpenAPI→Markdown generator for a plugin-ready API reference

## Architecture overview
- REST API: FastAPI app in `core/restapi/api.py`
- Knowledge base and ingestion:
    - Graph: `core/knowledgebase/MemgraphManager.py`, `CypherQueryHandler.py`
    - Vectors: `core/knowledgebase/notes/CollectionManager.py`, `Embeddings.py`, `Searcher.py`
    - Notes vault: `core/knowledgebase/notes/VaultManager.py`
    - GitHub repo: `core/knowledgebase/code/APIRepoManager.py`
- Bedrock authentication: `core/knowledgebase/AWSAuth.py`
- Prompts: `core/knowledgebase/prompts/`

Data flow:
1) Ingest notes/code → build graph in Memgraph and vectors in Chroma.
2) Query endpoints combine vector candidates with graph traversal/context.
3) Debug endpoints provide visibility into collections, scores, and schema.

## Installation

### Prerequisites
- Docker + Docker Compose (recommended)
- Or Python 3.9+ for local dev
- AWS credentials for Bedrock
- Memgraph reachable (local container or external)
- A directory for Chroma data

### Docker (recommended)
1) Clone:
```sh
git clone https://github.com/jakezp/bor.git
cd bor
```

2) Environment:
- Copy `.env.example` to `.env` and set AWS + service variables (see “Configuration”).

3) Build and run:
```sh
docker compose up --build -d
```

4) Visit:
- Docs: http://localhost:8000/docs
- OpenAPI: http://localhost:8000/openapi.json

### Local development
1) Create a virtualenv and install:
```sh
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

2) Ensure dependencies:
- Memgraph: run `bash core/run_memgraph_290.sh` (or your local install)
- Set `CHROMA_DATA_DIR` (folder for vectors/collections)

3) Run the API:
```sh
bash core/run_server.sh
# or
uvicorn core.restapi.api:app --reload
```

## Configuration
See `.env.example` and `core/knowledgebase/constants.py`.

- AWS Bedrock
    - BEDROCK_REGION
    - BEDROCK_MODEL_ID (LLM)
    - BEDROCK_EMBEDDING_MODEL (e.g., Titan v2)
- Memgraph
    - MEMGRAPH_HOST (default 127.0.0.1)
    - MEMGRAPH_PORT (default 7687)
- Chroma
    - CHROMA_DATA_DIR (absolute path to a writable folder)
    - CHROMA_VECTOR_SPACE (cosine)

## Running the server
- Docker:
```sh
docker compose up --build -d
```
- Local:
```sh
bash core/run_server.sh
```
Health check:
```sh
curl -s 'http://localhost:8000/knowledge_base/debug/health' | jq
```

## API and documentation

- Live docs: http://localhost:8000/docs
- Generated Markdown reference (for plugin developers):
    - File: `docs/API_REFERENCE.md`
    - Generate with VS Code task “Docs: Generate API Markdown” or:
        ```sh
        BASE_URL=http://localhost:8000 python scripts/generate_api_docs.py
        ```
- Endpoint catalog with notes/status: `docs/endpoints.md`

Key endpoints (improved):
- Notes: add/update/delete/rename files; get_for_path
- Vector: sentence_to_nodes, node_to_sentences, suggest_link
- Code: POST /knowledge_base/code/init_repo_from_api (owner/repo with ref/token)
- Debug: health, chroma, graph_overview, vector_scores
- Text Analyzer (JSON-first): optimize_style, explain, debug, generate_questions

## Usage examples (curl)

- Init a local Obsidian vault:
```sh
curl -X POST \
    'http://localhost:8000/knowledge_base/general/init_local_repo' \
    -H 'Content-Type: application/json' \
    -d '{"path":"/abs/path/to/vault","type":"Notes"}'
```

- Initialize a GitHub code repo (structure only):
```sh
curl -X POST \
    'http://localhost:8000/knowledge_base/code/init_repo_from_api' \
    -H 'Content-Type: application/json' \
    -d '{"owner":"vercel","repo":"next.js","ref":"canary"}'
```

- Vector debug scores:
```sh
curl -X POST \
    'http://localhost:8000/knowledge_base/debug/vector_scores?top_k=5' \
    -H 'Content-Type: application/json' \
    -d '{"repo":{"path":"/abs/path/to/vault","type":"Notes"}, "content":"Napoleon Bonaparte was born in Corsica."}'
```

- Text Analyzer (explain):
```sh
curl -X POST \
    'http://localhost:8000/knowledge_base/text_analizer/code/explain' \
    -H 'Content-Type: application/json' \
    -d '{"content":"def add(x,y): return x+y","language":"python","output_format":"json"}'
```

## Obsidian plugin notes
- Endpoints return JSON by default with stable schemas (see `docs/API_REFERENCE.md`).
- Notes endpoints accept absolute file paths. For add/update, you can pass full file content.
- Vector helpers:
    - sentence_to_nodes → map a snippet to node IDs
    - suggest_link → ranked candidate file paths
- Text Analyzer caps input at 6,000 characters (returns 400 if exceeded).
- CORS is permissive by default in `api.py`; tighten as necessary.

## Operations and smoke tests
- Debug:
    - `/knowledge_base/debug/health`
    - `/knowledge_base/debug/chroma`
    - `/knowledge_base/debug/graph_overview`
- Delete data:
    - `/knowledge_base/general/delete_all_for_repo`
    - `/knowledge_base/general/delete_all?purge=true` (with guardrails)
- Smoke tests: `scripts/smoke_tests.sh`
```sh
# Text Analyzer only
BASE_URL=http://localhost:8000 TEST_TA=true bash scripts/smoke_tests.sh

# Vector + suggest against a vault
BASE_URL=http://localhost:8000 \
REPO_PATH=/abs/path/to/vault \
TEST_VECTOR=true \
TEST_SUGGEST=true \
bash scripts/smoke_tests.sh
```
- VS Code tasks:
    - Rebuild + Smoke (TA) [default build task]
    - Rebuild + Smoke (Vault full)
    - Docs: Generate API Markdown
    - Rebuild + API Docs

## Contributing
- Please open issues/PRs for features, fixes, or docs improvements.
- When changing public endpoints, regenerate `docs/API_REFERENCE.md` and update `docs/endpoints.md`.
- Prefer adding or updating smoke tests alongside behavior changes.

## Acknowledgements & origin
This project is a fork of the BOR project by Memgraph:
- Upstream: https://github.com/memgraph/bor
- Fork: https://github.com/jakezp/bor

We’ve reworked ingestion (Obsidian vault, GitHub), moved to AWS Bedrock embeddings, stabilized vector search, added debug endpoints, and created documentation/tooling for smooth plugin integration.

## License
See the `LICENSE` file at the repository root for the full license text. This fork remains under the same license terms as upstream. For the upstream license, see:
- https://github.com/memgraph/bor/blob/main/LICENSE

