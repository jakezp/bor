# BOR API Endpoints Catalog

This document describes all FastAPI endpoints exposed by the backend, with request/response shapes and current review status. Use this as a checklist to safely iterate, test, and improve endpoints without regressing those already stabilized.

Legend
- [Improved] Endpoint has been recently hardened/updated and validated.
- [Reviewed] Endpoint reviewed for correctness; may still be improved later.
- [Pending] Endpoint not yet reviewed; improve and test next.

Note: Pydantic models used below come from `core/restapi/api.py`.
- Repo: { path: string, type?: "Notes" | "Code" }
- File: { path: string, type?: "Notes" | "Code", content?: string }
- Question: { repo: Repo, prompt: string, type?: "Notes" | "Code" }
- Answer: { content: string }
- Node: { repo: Repo, id: number }
- Sentence: { repo: Repo, content: string }
- Paragraph: { content: string }

---

## General

1) POST /knowledge_base/general/get_all_for_repo — [Improved]
- Purpose: Export repo-specific subgraph from Memgraph.
- Request: Repo
- Response: JSON list (mapped nodes/edges), or 204 when empty.
- Notes:
  - FastAPI /docs now includes request examples and descriptions.
  - Path normalization: server resolves to absolute path and strips trailing slashes before querying.
  - Robust export: no project() or path patterns; returns scalar fields only.
    - Nodes: id(n), labels(n), properties(n)
    - Relationships: id(r), id(start), id(end), type(r), properties(r)
  - Includes isolated nodes (nodes with no edges) because nodes and relationships are fetched separately and merged in Python.
  - Reads via `MemgraphManager.export_data_for_repo_path`.

2) DELETE /knowledge_base/general/delete_all_for_repo — [Improved]
- Purpose: Delete all graph data and vectors for a single repo.
- Request: Repo
- Response: { status: "ok", path } or { status: "error", message, path }
- Improvements:
  - Clears Memgraph for repo.
  - Deletes Chroma collection for repo.
  - Removes repo-specific vault state file `vault_state_<collection>.json`.

3) POST /knowledge_base/general/delete_all[?purge=true] — [Improved]
- Purpose: Delete ALL graph data and ALL Chroma collections; optionally purge CHROMA_DATA_DIR contents.
- Request: none (query `purge=true` optional)
- Response: { status: "ok", message, purge_report? } or error JSON
- Improvements:
  - Enumerates and deletes Chroma collections (avoids reset disabled).
  - Removes all vault_state_*.json.
  - Optional purge physically removes files under CHROMA_DATA_DIR with guardrails.

4) POST /knowledge_base/general/init_local_repo — [Improved]
- Purpose: Initialize from a local path. For Notes, ingests an Obsidian vault incrementally; for Code, generates Cypher from a local repo.
- Request: Repo
- Response (Notes): { type: "Notes", path, result: { new, modified, deleted, errors[] } }
- Response (Code): { type: "Code", path, status: "ok" }
- Improvements:
  - Returns structured stats.
  - Notes ingest uses per-repo state files; post-ingest normalization enforces labels and file/repo attributes; Bedrock-only embeddings with caching.

5) POST /knowledge_base/general/ask — [Improved]
  - FastAPI /docs now includes request examples and descriptions.
- Purpose: Ask a question against a repo (Notes or Code agent).
- Request: Question
- Response: Answer
 - Improvements:
   - Default agent type uses ZERO_SHOT_REACT_DESCRIPTION to avoid Bedrock "functions" payloads.
   - Agent type is configurable via env var LLM_AGENT_TYPE (ZERO_SHOT, STRUCTURED_ZERO_SHOT, FUNCTIONS).
   - Retains search_text, search_graph, and run_cypher_query tools; no provider-specific function schema.

6) POST /knowledge_base/general/get_schema — [Improved]
- Purpose: Generate a prompt-ready schema summary for a repo.
- Request: Repo
- Response: Answer (string schema)
- Improvements:
  - Path normalization to absolute before querying.
  - Clear failure surfaced as 500 with error detail; Swagger description expanded.

7) GET /knowledge_base/debug/state — [Reviewed]
- Purpose: Inspect vault state files under CHROMA_DATA_DIR; optional repo_path focus.
- Request: repo_path? (query)
- Response: { chroma_data_dir, all_state_files[], repo_state? }

8) GET /knowledge_base/debug/chroma — [Reviewed]
- Purpose: Inspect Chroma collections and filesystem contents.
- Request: none
- Response: { data_dir, exists, files[], collections[] }

9) GET /knowledge_base/debug/health — [Reviewed]
- Purpose: Quick service health check for Memgraph and Chroma; useful for regression detection.
- Request: repo_path? (query)
- Response: { memgraph: { status, nodes?, error? }, chroma: { status, collections?, error? } }

10) GET /knowledge_base/debug/graph_overview — [Reviewed]

11) POST /knowledge_base/debug/vector_scores — [Improved]
- Purpose: Return raw cosine similarity scores for a sentence against graph nodes (debugging aid).
- Request: Sentence { repo: Repo, content: string }
- Query params: top_k? (int, default 3, bounded 1..50)
- Response: {
    status: "ok",
    path: string,
    top_k: number,
    results: Array<{ node_id: number, score: number }>
  }
- Notes:
  - Uses the same embedding model (Bedrock Titan) and Memgraph vector search as production endpoints.
  - Computes cosine similarity in Cypher against a per-request Temp node; concurrency-safe.
  - Useful to inspect ranking stability and tune thresholds.
- Purpose: Inspect `repo_path` distribution on nodes/relationships and count objects under a given file path prefix; useful to diagnose why exports return empty/partial data.
- Request: repo_path? (query)
- Response: {
    node_repo_paths: [{ repo_path, cnt }],
    rel_repo_paths: [{ repo_path, cnt }],
    nodes_with_file_prefix?: { cnt },
    rels_with_file_prefix?: { cnt }
  }

---

## Notes endpoints

1) POST /knowledge_base/notes/get_for_path — [Reviewed]
- Purpose: Export file-specific subgraph.
- Request: File
- Response: JSON list (mapped nodes/edges) or 204.
 - FastAPI /docs: shows example body and clarifies that path must be absolute.

2) PUT /knowledge_base/notes/add_file — [Improved]
 - FastAPI /docs: shows example body and clarifies content usage (prefer providing content when vault isn’t mounted).
- Purpose: Add a single note file to the knowledge base and vectors.
- Request: File
- Response: { status: "ok", path } or error JSON
- Pipeline:
  - LLM to Cypher (CREATE or MERGE), multi-statement execution.
  - Add sentences to Chroma (Bedrock embeddings, cached).
  - Update Memgraph embeddings.
  - Post-ingest normalization (labels, file_path/repo_path on nodes/relationships).
  - Update per-repo state file.

3) PUT /knowledge_base/notes/update_file — [Improved]
 - FastAPI /docs: shows example body and clarifies that path must be absolute and when to provide content.
- Purpose: Update/replace a note file (delete + add).
- Request: File
- Response: { status: "ok", path } or error JSON
- Improvements: Same pipeline as add_file; ensures state consistency and normalization.
 - Notes for request fields:
   - path: Absolute file path inside the vault (e.g., /abs/path/to/vault/Note.md).
   - type: "Notes" (optional for this endpoint).
   - content: Provide full raw text of the note. If omitted, backend will try to read from the container filesystem at 'path'. Prefer providing content when the vault is not mounted into the container.

4) DELETE /knowledge_base/notes/delete_file — [Improved]
- Purpose: Delete a note’s graph and vectors and update state.
- Request: File
- Response: { status: "ok", path } or error JSON
- Improvements:
  - Now returns structured JSON and validates absolute path.
  - FastAPI /docs: example body and description updated.

5) POST /knowledge_base/notes/rename_file — [Improved]
 - FastAPI /docs: shows example bodies for old_file and new_file and describes fields.
- Purpose: Rename a file path in graph, relationships, and vectors; update state.
- Request: old_file: File, new_file: File
- Response: { status: "ok", old_path, new_path } or error JSON
- Improvements:
  - Returns JSON.
  - Updates relationship.file_path in addition to node.file_path.
  - Collection name handling hardened; repo path normalized absolute.

6) POST /knowledge_base/notes/node_to_sentences — [Improved]
- Purpose: Retrieve top-matching sentences (vector search) for a graph node.
- Request: Node
- Query params: top_k? (int, default 3)
- Response: Sentence[]
 - Implementation details:
   - Fetches node embeddings from Memgraph and queries Chroma with n_results=top_k.
   - Embeddings computed via Bedrock and cached; Chroma auto-embedding disabled.

7) POST /knowledge_base/notes/sentence_to_nodes — [Improved]
- Purpose: Find node IDs most similar to a sentence.
- Request: Sentence
- Query params: top_k? (int, default 1)
- Response: Node[]
 - Implementation details:
   - Computes sentence embedding via Bedrock; optionally uses Chroma to retrieve a candidate embedding when needed.
   - Performs graph vector search with a per-request Temp node and cosine in Cypher.
   - Excludes :Temp nodes from the corpus and orders by similarity.

8) POST /knowledge_base/notes/suggest_link — [Improved]
- Purpose: Suggest the most probable file(s) for a given text snippet.
- Request: Sentence
- Query params: top_k? (int, default 1)
- Response:
  - When top_k=1: File { path }
  - When top_k>1: { status: "ok", candidates: string[] } (ranked by similarity)
 - Implementation details:
   - Ranks candidate file paths via Chroma with Bedrock embeddings; returns unique, ordered paths.

---

## Code endpoints

1) POST /knowledge_base/code/init_repo_from_api — [Improved]
- Purpose: Initialize a code repo by fetching its directory structure via GitHub contents API and creating a Repo/Dir/File graph.
- Request: { owner: string, repo: string, ref?: string, token?: string }
- Response: { status: "ok", owner, repo, ref, nodes_created: number, relationships_created: number } or error JSON
- Notes:
  - The graph uses labels Repo, Dir, and File with CONTAINS relationships.
  - repo_path is set to a stable URI form: github://{owner}/{repo} for all created nodes.
  - Optional ref targets a branch or tag; optional token (GitHub PAT) increases rate limits and access to private repos.
  - Emits Cypher and executes via run_update_query with guardrails.
  - This is directory-structure-only; does not ingest file contents or code semantics.
  
Example request:
```
POST /knowledge_base/code/init_repo_from_api
{
  "owner": "vercel",
  "repo": "next.js",
  "ref": "canary"
}
```

---

## Text analyzer

1) POST /knowledge_base/text_analizer/code/optimize_style — [Improved]
- Purpose: Suggest code style improvements for a snippet.
- Request: { content: string, language?: string, style?: string, output_format?: "json" | "markdown" }
- Response (default JSON): { status: "ok", suggestions: Array<{ message: string, rule?: string, line?: number, before?: string, after?: string, severity?: string }>, summary?: string }
- Notes: 6000-char content cap; output_format=markdown returns a freeform string in Answer(content).

2) POST /knowledge_base/text_analizer/code/explain — [Improved]
- Purpose: Explain what a code snippet does.
- Request: { content: string, language?: string, output_format?: "json" | "markdown" }
- Response (JSON): { status: "ok", explanation: string, key_points?: string[] }
- Notes: 6000-char cap; markdown returns Answer(content).

3) POST /knowledge_base/text_analizer/code/debug — [Improved]
- Purpose: Provide debugging assistance and potential issues.
- Request: { content: string, language?: string, output_format?: "json" | "markdown" }
- Response (JSON): { status: "ok", issues: Array<{ title: string, rationale: string, severity?: string, fix_hint?: string }>, test_suggestions?: string[] }
- Notes: 6000-char cap; markdown returns Answer(content).

4) POST /knowledge_base/text_analizer/notes/generate_questions — [Improved]
- Purpose: Generate comprehension questions from a note paragraph.
- Request: { content: string, num_questions?: number, output_format?: "json" | "markdown" }
- Response (JSON): { status: "ok", questions: string[] }
- Notes: 6000-char cap; num_questions bounded 1..20 (default 5); markdown returns Answer(content).

---

## Current invariants and guardrails

- LLM Cypher emission tightened via prompts:
  - Every node must carry at least one label; fallback :Unknown if no taxonomy label fits.
  - CREATE/MERGE-only; semicolon-terminated; no standalone MATCH.
- Executor guardrail logs a warning when unlabeled node patterns are detected.
- Post-ingest normalization (per file):
  - Adds :Unknown to unlabeled nodes.
  - Backfills missing file_path/repo_path on nodes and relationships (NULL only).
- Vector store
  - Chroma collections created without internal embedding_function; embeddings computed via Bedrock (Titan) and cached by content hash.
- State management
  - Per-repo vault state files `vault_state_<collection>.json` under CHROMA_DATA_DIR; delete_all and delete_all_for_repo clean these appropriately.

## Maintenance and one-time repairs

- repo_path repair for legacy data
  - Where: `core/knowledgebase/MemgraphManager.py` → `fix_repo_path_for_repo(vault_root)` and `force_repo_path_for_file(file_path, repo_path)`.
  - How it runs: `core/knowledgebase/notes/VaultManager.py` calls `mm.fix_repo_path_for_repo(self.vault_path)` automatically at the end of `populate_vault()`. Trigger it by calling `POST /knowledge_base/general/init_local_repo` for your vault.
  - Effect: Sets repo_path on nodes/relationships to the absolute vault root when their file_path lives under that vault; leaves existing non-null repo_path values intact unless correcting within the vault scope.

---

## Checklist for next review passes

- General
  - get_all_for_repo [Improved]
  - ask [Improved]
  - get_schema [Improved]
- Notes
  - get_for_path [Reviewed]
  - delete_file [Improved]
  - node_to_sentences [Improved]
  - sentence_to_nodes [Improved]
  - suggest_link [Improved]
- Code
  - init_repo_from_api [Improved]
- Text analyzer
  - code/optimize_style [Improved]
  - code/explain [Improved]
  - code/debug [Improved]
  - notes/generate_questions [Improved]

For each Pending endpoint, we will:
1) Add/confirm structured JSON responses and error handling.
2) Ensure side effects update state consistently (where applicable).
3) Add light debug logging (where helpful) and avoid noisy logs.
4) Validate with a quick manual or scripted check, then mark as [Improved].

---

## Quick examples (curl)

- Init Notes repo
```
curl -X POST \
  'http://localhost:8000/knowledge_base/general/init_local_repo' \
  -H 'Content-Type: application/json' \
  -d '{"path":"/abs/path/to/vault","type":"Notes"}'
```

- Delete all (purge physical Chroma files)
```
curl -X POST 'http://localhost:8000/knowledge_base/general/delete_all?purge=true'
```

- Add or update a note file
```
curl -X PUT \
  'http://localhost:8000/knowledge_base/notes/update_file' \
  -H 'Content-Type: application/json' \
  -d '{"path":"/abs/path/to/vault/File.md","type":"Notes","content":"..."}'
```

- Inspect Chroma
```
curl -s 'http://localhost:8000/knowledge_base/debug/chroma' | jq
```

- Health check
```
curl -s 'http://localhost:8000/knowledge_base/debug/health' | jq
```

- Graph overview
```
curl -s 'http://localhost:8000/knowledge_base/debug/graph_overview?repo_path=/abs/path/to/vault' | jq
```

- Smoke tests (optional)
```
BASE_URL=http://localhost:8000 \
REPO_PATH=/abs/path/to/vault \
bash scripts/smoke_tests.sh
```

## API reference for plugin developers

We generate a Markdown API reference from the live OpenAPI schema so you have a single file with endpoints, parameters, and schemas:

- Output: `docs/API_REFERENCE.md`
- Source: pulled from the running server at `/openapi.json`.

Regenerate it any time:

- VS Code: Task "Docs: Generate API Markdown" (or the aggregate "Rebuild + API Docs").
- Terminal:

  ```sh
  BASE_URL=http://localhost:8000 python scripts/generate_api_docs.py
  ```

Share `docs/API_REFERENCE.md` with the Obsidian plugin developer to align request/response handling with the backend.

Maintained on branch: `feature/aws-bedrock-integration`.
