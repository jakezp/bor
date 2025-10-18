# FastAPI Reference

Version: 0.1.0  
Generated: 2025-10-17 17:17:11

This document is generated from the live OpenAPI schema (/openapi.json).

## POST /knowledge_base/code/init_repo_from_api

Init Repo From Api

### Request body
- required: true
- content-type: application/json
    - schema: RemoteRepo
    - type: object
    - properties:
      - owner*: string
      - repo*: string
      - ref: object
      - token: object

Example:

```json
{
  "owner": "org",
  "repo": "name",
  "ref": "main"
}
```

### Responses
- 200: Successful Response
  - content-type: application/json
        - type: object
- 422: Validation Error
  - content-type: application/json
        - schema: HTTPValidationError
        - type: object
        - properties:
          - detail: array
            - items: object

## GET /knowledge_base/debug/chroma

Debug Chroma

Chroma collections and filesystem status.

Helps verify cleanup after delete operations and inspect collection counts.

### Responses
- 200: Successful Response
  - content-type: application/json
        - type: object

## GET /knowledge_base/debug/graph_overview

Debug Graph Overview

Repo_path distribution and file_path prefix counts.

Query params:
- repo_path (optional): Absolute vault path to count nodes/rels whose file_path is under the prefix.

### Parameters
- repo_path [query] : object

### Responses
- 200: Successful Response
  - content-type: application/json
        - type: object
- 422: Validation Error
  - content-type: application/json
        - schema: HTTPValidationError
        - type: object
        - properties:
          - detail: array
            - items: object

## GET /knowledge_base/debug/health

Debug Health

Quick health report for Memgraph and Chroma.

Query params:
- repo_path (optional): When provided, the Chroma section is computed for that repo.

### Parameters
- repo_path [query] : object

### Responses
- 200: Successful Response
  - content-type: application/json
        - type: object
- 422: Validation Error
  - content-type: application/json
        - schema: HTTPValidationError
        - type: object
        - properties:
          - detail: array
            - items: object

## GET /knowledge_base/debug/state

Debug State

State files under CHROMA_DATA_DIR.

Query params:
- repo_path (optional): Absolute repo/vault path to compute the expected vault_state file name.

### Parameters
- repo_path [query] : object

### Responses
- 200: Successful Response
  - content-type: application/json
        - type: object
- 422: Validation Error
  - content-type: application/json
        - schema: HTTPValidationError
        - type: object
        - properties:
          - detail: array
            - items: object

## POST /knowledge_base/debug/vector_scores

Debug Vector Scores

Debug-only endpoint to inspect raw vector similarity scores for a sentence.

Query params:
- top_k (default 3, bounded 1..50)

### Parameters
- top_k [query] : integer

### Request body
- required: true
- content-type: application/json
    - schema: Sentence
    - type: object
    - properties:
      - repo*: object
      - content*: string

Example:

```json
{
  "repo": {
    "path": "/abs/path/to/vault",
    "type": "Notes"
  },
  "content": "Napoleon Bonaparte was born in Corsica."
}
```

### Responses
- 200: Successful Response
  - content-type: application/json
        - schema: VectorDebugResponse
        - type: object
        - properties:
          - status*: string
          - path*: string
          - top_k*: integer
          - results*: array
            - items: object
- 422: Validation Error
  - content-type: application/json
        - schema: HTTPValidationError
        - type: object
        - properties:
          - detail: array
            - items: object

## POST /knowledge_base/general/ask

Ask Repo

### Request body
- required: true
- content-type: application/json
    - schema: Question
    - type: object
    - properties:
      - repo*: object
      - prompt*: string
      - type: object

Example:

```json
{
  "repo": {
    "path": "/abs/path/to/vault",
    "type": "Notes"
  },
  "prompt": "Tell me about ...",
  "type": "Notes"
}
```

### Responses
- 200: Successful Response
  - content-type: application/json
        - schema: Answer
        - type: object
        - properties:
          - content*: string
- 422: Validation Error
  - content-type: application/json
        - schema: HTTPValidationError
        - type: object
        - properties:
          - detail: array
            - items: object

## POST /knowledge_base/general/delete_all

Delete All

### Parameters
- purge [query] : boolean

### Responses
- 200: Successful Response
  - content-type: application/json
        - type: object
- 422: Validation Error
  - content-type: application/json
        - schema: HTTPValidationError
        - type: object
        - properties:
          - detail: array
            - items: object

## DELETE /knowledge_base/general/delete_all_for_repo

Delete All For Repo

### Request body
- required: true
- content-type: application/json
    - schema: Repo
    - type: object
    - properties:
      - path*: string
      - type: object

Example:

```json
{
  "path": "/abs/path/to/vault",
  "type": "Notes"
}
```

### Responses
- 200: Successful Response
  - content-type: application/json
        - type: object
- 422: Validation Error
  - content-type: application/json
        - schema: HTTPValidationError
        - type: object
        - properties:
          - detail: array
            - items: object

## POST /knowledge_base/general/get_all_for_repo

Get All For Repo

### Request body
- required: true
- content-type: application/json
    - schema: Repo
    - type: object
    - properties:
      - path*: string
      - type: object

Example:

```json
{
  "path": "/abs/path/to/vault",
  "type": "Notes"
}
```

### Responses
- 200: Successful Response
  - content-type: application/json
        - type: object
- 422: Validation Error
  - content-type: application/json
        - schema: HTTPValidationError
        - type: object
        - properties:
          - detail: array
            - items: object

## POST /knowledge_base/general/get_schema

Get Schema

### Request body
- required: true
- content-type: application/json
    - schema: Repo
    - type: object
    - properties:
      - path*: string
      - type: object

Example:

```json
{
  "path": "/abs/path/to/vault",
  "type": "Notes"
}
```

### Responses
- 200: Successful Response
  - content-type: application/json
        - schema: Answer
        - type: object
        - properties:
          - content*: string
- 422: Validation Error
  - content-type: application/json
        - schema: HTTPValidationError
        - type: object
        - properties:
          - detail: array
            - items: object

## POST /knowledge_base/general/init_local_repo

Init Repo

### Request body
- required: true
- content-type: application/json
    - schema: Repo
    - type: object
    - properties:
      - path*: string
      - type: object

Example:

```json
{
  "path": "/abs/path/to/vault",
  "type": "Notes"
}
```

### Responses
- 200: Successful Response
  - content-type: application/json
        - type: object
- 422: Validation Error
  - content-type: application/json
        - schema: HTTPValidationError
        - type: object
        - properties:
          - detail: array
            - items: object

## PUT /knowledge_base/notes/add_file

Add File

Add a single note file and index it in Memgraph + Chroma.

### Request body
- required: true
- content-type: application/json
    - schema: File
    - type: object
    - properties:
      - path*: string
      - type: object
      - content: object

Example:

```json
{
  "path": "/abs/path/to/vault/New Note.md",
  "type": "Notes",
  "content": "# New Note\n..."
}
```

### Responses
- 200: Successful Response
  - content-type: application/json
        - type: object
- 422: Validation Error
  - content-type: application/json
        - schema: HTTPValidationError
        - type: object
        - properties:
          - detail: array
            - items: object

## DELETE /knowledge_base/notes/delete_file

Delete File

### Request body
- required: true
- content-type: application/json
    - schema: File
    - type: object
    - properties:
      - path*: string
      - type: object
      - content: object

Example:

```json
{
  "path": "/abs/path/to/vault/Note.md",
  "type": "Notes"
}
```

### Responses
- 200: Successful Response
  - content-type: application/json
        - type: object
- 422: Validation Error
  - content-type: application/json
        - schema: HTTPValidationError
        - type: object
        - properties:
          - detail: array
            - items: object

## POST /knowledge_base/notes/get_for_path

Get For Path

### Request body
- required: true
- content-type: application/json
    - schema: File
    - type: object
    - properties:
      - path*: string
      - type: object
      - content: object

Example:

```json
{
  "path": "/abs/path/to/vault/Note.md",
  "type": "Notes"
}
```

### Responses
- 200: Successful Response
  - content-type: application/json
        - type: object
- 422: Validation Error
  - content-type: application/json
        - schema: HTTPValidationError
        - type: object
        - properties:
          - detail: array
            - items: object

## POST /knowledge_base/notes/node_to_sentences

Node To Sentences

### Parameters
- top_k [query] : integer

### Request body
- required: true
- content-type: application/json
    - schema: Node
    - type: object
    - properties:
      - repo*: object
      - id*: integer

Example:

```json
{
  "repo": {
    "path": "/abs/path/to/vault",
    "type": "Notes"
  },
  "id": 123
}
```

### Responses
- 200: Successful Response
  - content-type: application/json
        - schema: Response Node To Sentences Knowledge Base Notes Node To Sentences Post
        - type: array
        - items:
          - schema: Sentence
          - type: object
          - properties:
            - repo*: object
            - content*: string
- 422: Validation Error
  - content-type: application/json
        - schema: HTTPValidationError
        - type: object
        - properties:
          - detail: array
            - items: object

## POST /knowledge_base/notes/rename_file

Rename File

### Request body
- required: true
- content-type: application/json
    - schema: Body_rename_file_knowledge_base_notes_rename_file_post
    - type: object
    - properties:
      - old_file*: object
        - desc: Represents a file in a repo.

path: Absolute path to the file on disk inside the selected repo/vault.
type: "Notes" or "Code" (optional; inferred by notes/* endpoints when omitted).
content: Raw UTF-8 text of the file when creating/updating via API. If omitted, the backend
         will attempt to read from the container filesystem at `path`. Provide content when
         the vault path is not mounted into the container.
      - new_file*: object
        - desc: Represents a file in a repo.

path: Absolute path to the file on disk inside the selected repo/vault.
type: "Notes" or "Code" (optional; inferred by notes/* endpoints when omitted).
content: Raw UTF-8 text of the file when creating/updating via API. If omitted, the backend
         will attempt to read from the container filesystem at `path`. Provide content when
         the vault path is not mounted into the container.

### Responses
- 200: Successful Response
  - content-type: application/json
        - type: object
- 422: Validation Error
  - content-type: application/json
        - schema: HTTPValidationError
        - type: object
        - properties:
          - detail: array
            - items: object

## POST /knowledge_base/notes/sentence_to_nodes

Sentence To Nodes

### Parameters
- top_k [query] : integer

### Request body
- required: true
- content-type: application/json
    - schema: Sentence
    - type: object
    - properties:
      - repo*: object
      - content*: string

Example:

```json
{
  "repo": {
    "path": "/abs/path/to/vault",
    "type": "Notes"
  },
  "content": "some sentence"
}
```

### Responses
- 200: Successful Response
  - content-type: application/json
        - schema: Response Sentence To Nodes Knowledge Base Notes Sentence To Nodes Post
        - type: array
        - items:
          - schema: Node
          - type: object
          - properties:
            - repo*: object
            - id*: integer
- 422: Validation Error
  - content-type: application/json
        - schema: HTTPValidationError
        - type: object
        - properties:
          - detail: array
            - items: object

## POST /knowledge_base/notes/suggest_link

Suggest Link

### Parameters
- top_k [query] : integer

### Request body
- required: true
- content-type: application/json
    - schema: Sentence
    - type: object
    - properties:
      - repo*: object
      - content*: string

Example:

```json
{
  "repo": {
    "path": "/abs/path/to/vault",
    "type": "Notes"
  },
  "content": "snippet of text"
}
```

### Responses
- 200: Successful Response
  - content-type: application/json
        - type: object
- 422: Validation Error
  - content-type: application/json
        - schema: HTTPValidationError
        - type: object
        - properties:
          - detail: array
            - items: object

## PUT /knowledge_base/notes/update_file

Update File

Update/replace a note file (delete + add) and refresh embeddings.

Recommended: Provide 'content' so ingestion doesn't rely on container file mounts.

### Request body
- required: true
- content-type: application/json
    - schema: File
    - type: object
    - properties:
      - path*: string
      - type: object
      - content: object

Example:

```json
{
  "path": "/abs/path/to/vault/Note.md",
  "type": "Notes",
  "content": "# Title\nBody text..."
}
```

### Responses
- 200: Successful Response
  - content-type: application/json
        - type: object
- 422: Validation Error
  - content-type: application/json
        - schema: HTTPValidationError
        - type: object
        - properties:
          - detail: array
            - items: object

## POST /knowledge_base/text_analizer/code/debug

Debug Code

### Request body
- required: true
- content-type: application/json
    - schema: CodeAnalysisRequest
    - type: object
    - properties:
      - content*: string
      - language: object
      - style: object
      - output_format: object

Example:

```json
{
  "content": "def foo(x): return x+1 # bug?",
  "language": "python",
  "output_format": "json"
}
```

### Responses
- 200: Successful Response
  - content-type: application/json
        - schema: Response Debug Code Knowledge Base Text Analizer Code Debug Post
        - type: object
- 422: Validation Error
  - content-type: application/json
        - schema: HTTPValidationError
        - type: object
        - properties:
          - detail: array
            - items: object

## POST /knowledge_base/text_analizer/code/explain

Explain Code

### Request body
- required: true
- content-type: application/json
    - schema: CodeAnalysisRequest
    - type: object
    - properties:
      - content*: string
      - language: object
      - style: object
      - output_format: object

Example:

```json
{
  "content": "def foo(x): return x+1",
  "language": "python",
  "output_format": "json"
}
```

### Responses
- 200: Successful Response
  - content-type: application/json
        - schema: Response Explain Code Knowledge Base Text Analizer Code Explain Post
        - type: object
- 422: Validation Error
  - content-type: application/json
        - schema: HTTPValidationError
        - type: object
        - properties:
          - detail: array
            - items: object

## POST /knowledge_base/text_analizer/code/optimize_style

Optimize Syle

### Request body
- required: true
- content-type: application/json
    - schema: CodeAnalysisRequest
    - type: object
    - properties:
      - content*: string
      - language: object
      - style: object
      - output_format: object

Example:

```json
{
  "content": "def foo():\n    pass",
  "language": "python",
  "style": "pep8",
  "output_format": "json"
}
```

### Responses
- 200: Successful Response
  - content-type: application/json
        - schema: Response Optimize Syle Knowledge Base Text Analizer Code Optimize Style Post
        - type: object
- 422: Validation Error
  - content-type: application/json
        - schema: HTTPValidationError
        - type: object
        - properties:
          - detail: array
            - items: object

## POST /knowledge_base/text_analizer/notes/generate_questions

Generate Questions

### Request body
- required: true
- content-type: application/json
    - schema: QuestionsRequest
    - type: object
    - properties:
      - content*: string
      - num_questions: object
      - output_format: object

Example:

```json
{
  "content": "# Note title\nSome text...",
  "num_questions": 5,
  "output_format": "json"
}
```

### Responses
- 200: Successful Response
  - content-type: application/json
        - schema: Response Generate Questions Knowledge Base Text Analizer Notes Generate Questions Post
        - type: object
- 422: Validation Error
  - content-type: application/json
        - schema: HTTPValidationError
        - type: object
        - properties:
          - detail: array
            - items: object
