from typing import Union, List
import os
import logging

from enum import Enum
from core.knowledgebase.Utils import Utils

from fastapi import FastAPI, status, Response, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel
from fastapi import Body

from core.knowledgebase import constants
from core.knowledgebase.AWSAuth import AWSAuthenticator

from core.knowledgebase.Initializer import Initializer
from core.knowledgebase.MemgraphManager import MemgraphManager
from core.knowledgebase.TextAnalizer import TextAnalizer
from core.knowledgebase.QueryAgents import NotesQueryAgent, CodeQueryAgent

from core.knowledgebase.notes.VaultManager import VaultManager
from core.knowledgebase.notes.CollectionManager import CollectionManager
from core.knowledgebase.notes.Searcher import Searcher

from core.knowledgebase.code.APIRepoManager import APIRepoManager
from core.knowledgebase.code.LocalRepoManager import LocalRepoManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Type(Enum):
    NOTES = "Notes"
    CODE = "Code"


class Repo(BaseModel):
    path: str
    type: Union[Type, None] = None


class RemoteRepo(BaseModel):
    owner: str
    repo: str
    ref: Union[str, None] = None
    token: Union[str, None] = None


class File(BaseModel):
    """Represents a file in a repo.

    path: Absolute path to the file on disk inside the selected repo/vault.
    type: "Notes" or "Code" (optional; inferred by notes/* endpoints when omitted).
    content: Raw UTF-8 text of the file when creating/updating via API. If omitted, the backend
             will attempt to read from the container filesystem at `path`. Provide content when
             the vault path is not mounted into the container.
    """
    path: str
    type: Union[Type, None] = None
    content: Union[str, None] = None


class Question(BaseModel):
    repo: Repo
    prompt: str
    type: Union[Type, None] = None


class Answer(BaseModel):
    content: str


class Node(BaseModel):
    repo: Repo
    id: int


class Sentence(BaseModel):
    repo: Repo
    content: str


class Paragraph(BaseModel):
    content: str


class NodeScore(BaseModel):
    node_id: int
    score: float


class VectorDebugResponse(BaseModel):
    status: str
    path: str
    top_k: int
    results: List[NodeScore]


# -------- Text Analyzer models (JSON-first) --------
class CodeAnalysisRequest(BaseModel):
    content: str
    language: Union[str, None] = None
    style: Union[str, None] = None  # optimize_style only
    output_format: Union[str, None] = None  # "json" (default) or "markdown"


class OptimizeStyleResponse(BaseModel):
    status: str
    suggestions: List[dict] = []  # { message, rule?, line?, before?, after?, severity? }
    summary: Union[str, None] = None


class ExplainResponse(BaseModel):
    status: str
    explanation: str
    key_points: List[str] = []


class DebugIssue(BaseModel):
    title: str
    rationale: str
    severity: Union[str, None] = None
    fix_hint: Union[str, None] = None


class DebugResponse(BaseModel):
    status: str
    issues: List[DebugIssue] = []
    test_suggestions: List[str] = []


class QuestionsRequest(BaseModel):
    content: str
    num_questions: Union[int, None] = 5
    output_format: Union[str, None] = None  # "json" (default) or "markdown"


class QuestionsResponse(BaseModel):
    status: str
    questions: List[str]


app = FastAPI()
mm = MemgraphManager()
ta = TextAnalizer()


@app.on_event("startup")
async def startup() -> None:
    # Log AWS authentication method being used
    try:
        # Reduce botocore.tokens noise
        logging.getLogger('botocore.tokens').setLevel(logging.WARNING)
        authenticator = AWSAuthenticator()
        auth_method = authenticator.get_auth_method()
        logger.info(f"🔐 AWS Bedrock Authentication: {auth_method}")
        logger.info(f"🌍 Bedrock Region: {constants.BEDROCK_REGION}")
        logger.info(f"🤖 Bedrock Model: {constants.BEDROCK_MODEL_ID}")
        logger.info(f"📊 Embedding Model: {constants.BEDROCK_EMBEDDING_MODEL}")
    except Exception as e:
        logger.error(f"❌ AWS Authentication Error: {e}")
    
    # Initialize mock data if needed
    # if constants.MOCK and mm.check_if_db_empty():
    #     Initializer.init_vault_data()
    return


@app.post("/knowledge_base/general/get_all_for_repo")
def get_all_for_repo(
    repo: Repo = Body(
        ...,
        example={"path": "/abs/path/to/vault", "type": "Notes"},
        description="Export the subgraph for a specific repo/vault. Path must be absolute.",
    )
) -> Response:
    # Normalize path to match how repo_path is stored in Memgraph (absolute, no trailing slash)
    try:
        norm_path = os.path.normpath(os.path.abspath(repo.path))
    except Exception:
        norm_path = repo.path
    data = mm.export_data_for_repo_path(norm_path)
    if data:
        json_data = jsonable_encoder(data)
        return JSONResponse(content=json_data)
    else:
        return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.delete("/knowledge_base/general/delete_all_for_repo")
def delete_all_for_repo(
    repo: Repo = Body(
        ...,
        example={"path": "/abs/path/to/vault", "type": "Notes"},
        description="Delete Memgraph data and Chroma collection for this repo. Also removes its vault_state file.",
    )
):
    try:
        try:
            norm_path = os.path.normpath(os.path.abspath(repo.path))
        except Exception:
            norm_path = repo.path
        mm.delete_all_for_repo(norm_path)
        if repo.type == Type.NOTES:
            cm = CollectionManager(norm_path)
            cm.delete_all_from_collection()
            # Remove repo-specific state file
            try:
                coll = Utils.collection_name_from_repo_path(norm_path)
                state_path = os.path.join(constants.CHROMA_DATA_DIR or ".", f"vault_state_{coll}.json")
                if os.path.exists(state_path):
                    os.remove(state_path)
            except Exception:
                pass
        return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ok", "path": norm_path})
    except Exception as e:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "message": str(e), "path": repo.path})

@app.get("/knowledge_base/debug/state")
def debug_state(repo_path: str | None = None):
    """State files under CHROMA_DATA_DIR.

    Query params:
    - repo_path (optional): Absolute repo/vault path to compute the expected vault_state file name.
    """
    try:
        state_dir = constants.CHROMA_DATA_DIR or "."
        files_info: List[dict] = []
        try:
            for fname in os.listdir(state_dir):
                if fname.startswith("vault_state_") and fname.endswith(".json"):
                    fpath = os.path.join(state_dir, fname)
                    try:
                        size = os.path.getsize(fpath)
                    except Exception:
                        size = None
                    try:
                        mtime = os.path.getmtime(fpath)
                    except Exception:
                        mtime = None
                    files_info.append({
                        "name": fname,
                        "path": fpath,
                        "exists": os.path.exists(fpath),
                        "size": size,
                        "mtime": mtime,
                    })
        except FileNotFoundError:
            pass

        repo_state = None
        if repo_path:
            coll = Utils.collection_name_from_repo_path(repo_path)
            rpath = os.path.join(state_dir, f"vault_state_{coll}.json")
            try:
                rsize = os.path.getsize(rpath)
            except Exception:
                rsize = None
            try:
                rmtime = os.path.getmtime(rpath)
            except Exception:
                rmtime = None
            repo_state = {
                "collection": coll,
                "path": rpath,
                "exists": os.path.exists(rpath),
                "size": rsize,
                "mtime": rmtime,
            }

        return JSONResponse(status_code=status.HTTP_200_OK, content={
            "chroma_data_dir": state_dir,
            "all_state_files": files_info,
            "repo_state": repo_state,
        })
    except Exception as e:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "message": str(e)})


@app.get("/knowledge_base/debug/chroma")
def debug_chroma():
    """Chroma collections and filesystem status.

    Helps verify cleanup after delete operations and inspect collection counts.
    """
    try:
        cm = CollectionManager()
        data_dir = constants.CHROMA_DATA_DIR or "."
        dir_exists = os.path.isdir(data_dir)
        files = []
        if dir_exists:
            try:
                for root, dirs, filenames in os.walk(data_dir):
                    for fn in filenames:
                        fpath = os.path.join(root, fn)
                        try:
                            size = os.path.getsize(fpath)
                        except Exception:
                            size = None
                        files.append({"path": fpath, "size": size})
            except Exception:
                pass

        collections_info = []
        try:
            cols = cm.chroma_client.list_collections()
            for col in cols:
                name = getattr(col, 'name', None) or (col.get('name') if isinstance(col, dict) else None)
                count = None
                if name:
                    try:
                        cobj = cm.chroma_client.get_collection(name=name)
                        # Prefer count() if available
                        if hasattr(cobj, 'count'):
                            count = cobj.count()
                        else:
                            count = None
                    except Exception:
                        pass
                collections_info.append({"name": name, "count": count})
        except Exception:
            pass

        return JSONResponse(status_code=status.HTTP_200_OK, content={
            "data_dir": data_dir,
            "exists": dir_exists,
            "files": files,
            "collections": collections_info,
        })
    except Exception as e:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "message": str(e)})


@app.get("/knowledge_base/debug/health")
def debug_health(repo_path: str | None = None):
    """Quick health report for Memgraph and Chroma.

    Query params:
    - repo_path (optional): When provided, the Chroma section is computed for that repo.
    """
    report: dict = {"memgraph": {}, "chroma": {}}
    # Memgraph check
    try:
        count = None
        try:
            res = mm.run_select_query("MATCH (n) RETURN count(n) AS nodes")
            first = next(res, None)
            if first and isinstance(first, dict):
                count = first.get("nodes")
        except Exception as e:
            report["memgraph"]["error"] = str(e)
        report["memgraph"].update({"status": "ok" if count is not None else "error", "nodes": count})
    except Exception as e:
        report["memgraph"] = {"status": "error", "error": str(e)}

    # Chroma check
    try:
        cm = CollectionManager(repo_path) if repo_path else CollectionManager()
        cols = []
        try:
            for col in cm.chroma_client.list_collections():
                name = getattr(col, 'name', None) or (col.get('name') if isinstance(col, dict) else None)
                cols.append(name)
        except Exception as e:
            report["chroma"]["error"] = str(e)
        report["chroma"].update({"status": "ok", "collections": cols})
    except Exception as e:
        report["chroma"] = {"status": "error", "error": str(e)}

    return JSONResponse(status_code=status.HTTP_200_OK, content=report)


@app.get("/knowledge_base/debug/graph_overview")
def debug_graph_overview(repo_path: str | None = None):
    """Repo_path distribution and file_path prefix counts.

    Query params:
    - repo_path (optional): Absolute vault path to count nodes/rels whose file_path is under the prefix.
    """
    overview: dict = {}
    try:
        # Distinct repo_path values on nodes
        rows = list(mm.run_select_query("MATCH (n) RETURN n.repo_path AS repo_path, count(n) AS cnt ORDER BY cnt DESC"))
        overview["node_repo_paths"] = rows
    except Exception as e:
        overview["node_repo_paths_error"] = str(e)
    try:
        # Distinct repo_path values on relationships
        rows = list(mm.run_select_query("MATCH ()-[r]->() RETURN r.repo_path AS repo_path, count(r) AS cnt ORDER BY cnt DESC"))
        overview["rel_repo_paths"] = rows
    except Exception as e:
        overview["rel_repo_paths_error"] = str(e)
    if repo_path:
        try:
            prefix = os.path.normpath(os.path.abspath(repo_path)) + "/"
        except Exception:
            prefix = repo_path + "/"
        try:
            row = next(mm.run_select_query(f"MATCH (n) WHERE n.file_path STARTS WITH '{prefix}' RETURN count(n) AS cnt"), None)
            overview["nodes_with_file_prefix"] = row
        except Exception as e:
            overview["nodes_with_file_prefix_error"] = str(e)
        try:
            row = next(mm.run_select_query(f"MATCH ()-[r]->() WHERE r.file_path STARTS WITH '{prefix}' RETURN count(r) AS cnt"), None)
            overview["rels_with_file_prefix"] = row
        except Exception as e:
            overview["rels_with_file_prefix_error"] = str(e)
    return JSONResponse(status_code=status.HTTP_200_OK, content=overview)


@app.post("/knowledge_base/debug/vector_scores", response_model=VectorDebugResponse)
def debug_vector_scores(
    sentence: Sentence = Body(
        ...,
        example={
            "repo": {"path": "/abs/path/to/vault", "type": "Notes"},
            "content": "Napoleon Bonaparte was born in Corsica."
        },
        description=(
            "Return cosine similarity scores for the top_k most similar graph nodes to the given sentence "
            "using the same embedding and Memgraph vector search pipeline as production endpoints."
        ),
    ),
    top_k: int = 3,
) -> VectorDebugResponse:
    """Debug-only endpoint to inspect raw vector similarity scores for a sentence.

    Query params:
    - top_k (default 3, bounded 1..50)
    """
    try:
        # Validate top_k
        try:
            k = max(1, min(50, int(top_k)))
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid top_k; must be an integer")

        # Normalize path
        try:
            norm_path = os.path.normpath(os.path.abspath(sentence.repo.path))
        except Exception:
            norm_path = sentence.repo.path

        # Perform search via Searcher
        searcher = Searcher(norm_path)
        rows = searcher.search_graph(query_text=sentence.content, limit=k)

        results: List[NodeScore] = []
        for row in rows:
            try:
                node_id = row.get('ID(node1)') if isinstance(row, dict) else None
                score = row.get('cosine_similarity') if isinstance(row, dict) else None
            except Exception:
                node_id = None
                score = None
            if node_id is None:
                # Fallback attempts
                try:
                    node_id = row['ID(m)'] if isinstance(row, dict) else None
                except Exception:
                    pass
            if score is None:
                try:
                    score = row['score'] if isinstance(row, dict) else None
                except Exception:
                    pass
            if node_id is not None and score is not None:
                results.append(NodeScore(node_id=int(node_id), score=float(score)))

        return VectorDebugResponse(status="ok", path=norm_path, top_k=k, results=results)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"vector_scores error: {e}")

@app.post("/knowledge_base/general/ask")
def ask_repo(
    question: Question = Body(
        ...,
        example={
            "repo": {"path": "/abs/path/to/vault", "type": "Notes"},
            "prompt": "Tell me about ...",
            "type": "Notes"
        },
        description=(
            "Ask a question over the repo using a non-functions agent (default ZERO_SHOT). "
            "Override via env LLM_AGENT_TYPE if needed."
        ),
    )
) -> Answer:
    if question.type == Type.NOTES:
        na = NotesQueryAgent(question.repo.path)
        return Answer(content=na.ask(question.prompt))

    ca = CodeQueryAgent(question.repo.path)
    return Answer(content=ca.ask(question.prompt))


@app.post("/knowledge_base/general/get_schema")
def get_schema(
    repo: Repo = Body(
        ...,
        example={"path": "/abs/path/to/vault", "type": "Notes"},
        description=(
            "Return a prompt-ready graph schema summary for the specified repo path. "
            "The server normalizes the path to an absolute path before querying."
        ),
    )
) -> Answer:
    try:
        try:
            norm_path = os.path.normpath(os.path.abspath(repo.path))
        except Exception:
            norm_path = repo.path
        schema = mm.get_schema_for_repo(norm_path)
        return Answer(content=schema or "")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"get_schema error: {e}")

# TODO: test with GPT4


@app.post("/knowledge_base/general/init_local_repo")
def init_repo(
    repo: Repo = Body(
        ...,
        example={"path": "/abs/path/to/vault", "type": "Notes"},
        description="Initialize Notes: incremental ingest; Code: generate Cypher from local repo.",
    )
):
    if repo.type == Type.CODE:
        lrm = LocalRepoManager(repo.path)
        cypher = lrm.generate_cypher()
        mm.run_update_query(cypher)
        return {"type": "Code", "path": repo.path, "status": "ok"}
    vm = VaultManager(repo.path)
    stats = vm.populate_vault()
    return {"type": "Notes", "path": repo.path, "result": stats}


@app.post("/knowledge_base/general/delete_all")
def delete_all(purge: bool = False):
    try:
        mm = MemgraphManager()
        cm = CollectionManager()
        mm.delete_all()
        cm.delete_all()
        # Remove all vault_state_*.json so next init does a full re-ingest
        try:
            state_dir = constants.CHROMA_DATA_DIR or "."
            for fname in os.listdir(state_dir):
                if fname.startswith("vault_state_") and fname.endswith(".json"):
                    try:
                        os.remove(os.path.join(state_dir, fname))
                    except Exception:
                        pass
        except Exception:
            pass
        purge_report = None
        if purge:
            # Physically remove files under CHROMA_DATA_DIR with safety checks
            data_dir = constants.CHROMA_DATA_DIR
            if not data_dir:
                return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={
                    "status": "error",
                    "message": "Purge requested but CHROMA_DATA_DIR is not set. Set it to a dedicated directory and retry.",
                })
            abs_dir = os.path.abspath(data_dir)
            # Basic guardrails: don't allow purging root or project root; require path name contains 'chroma'
            base_name = os.path.basename(abs_dir)
            if abs_dir in ("/", os.path.expanduser("~")) or base_name.lower().find("chroma") == -1:
                return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={
                    "status": "error",
                    "message": f"Refusing to purge unsafe directory: {abs_dir}. Ensure CHROMA_DATA_DIR points to a dedicated chroma-specific folder.",
                })
            removed, failed = [], []
            # Best-effort removal of contents (leave base dir present)
            try:
                for root, dirs, files in os.walk(abs_dir, topdown=False):
                    for fn in files:
                        fpath = os.path.join(root, fn)
                        try:
                            os.remove(fpath)
                            removed.append(fpath)
                        except Exception as e:
                            failed.append({"path": fpath, "error": str(e)})
                    for dn in dirs:
                        dpath = os.path.join(root, dn)
                        try:
                            os.rmdir(dpath)
                            removed.append(dpath)
                        except Exception as e:
                            # Likely open handles or non-empty; record and continue
                            failed.append({"path": dpath, "error": str(e)})
            except Exception as e:
                failed.append({"path": abs_dir, "error": str(e)})
            purge_report = {"directory": abs_dir, "removed": removed, "failed": failed}

        return JSONResponse(status_code=status.HTTP_200_OK, content={
            "status": "ok",
            "message": "Graph and vector store cleared",
            **({"purge_report": purge_report} if purge else {}),
        })
    except Exception as e:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "message": str(e)})


MAX_TA_CHARS = 6000


@app.post("/knowledge_base/text_analizer/code/optimize_style", response_model=Union[OptimizeStyleResponse, Answer])
def optimize_syle(
    body: CodeAnalysisRequest = Body(
        ...,
        example={"content": "def foo():\n    pass", "language": "python", "style": "pep8", "output_format": "json"},
        description="Suggest code style improvements for a snippet. Default output_format=json; pass markdown to get a freeform string.",
    )
) -> Union[OptimizeStyleResponse, Answer]:
    # Validate
    if body is None or (not isinstance(body.content, str)) or (len(body.content.strip()) == 0):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="content is empty")
    if len(body.content) > MAX_TA_CHARS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"content exceeds {MAX_TA_CHARS} characters; please trim")
    ta = TextAnalizer()
    # For now we keep prompts simple; future: condition on body.language/body.style
    content = ta.optimize_code_style(body.content)
    # Markdown fallback
    if (body.output_format or "json").lower() == "markdown":
        return Answer(content=content)
    # Heuristic shaping into JSON suggestions; keep minimal to avoid brittle parsing
    suggestions: List[dict] = []
    if content:
        suggestions.append({"message": content})
    return OptimizeStyleResponse(status="ok", suggestions=suggestions)


@app.post("/knowledge_base/text_analizer/code/explain", response_model=Union[ExplainResponse, Answer])
def explain_code(
    body: CodeAnalysisRequest = Body(
        ...,
        example={"content": "def foo(x): return x+1", "language": "python", "output_format": "json"},
        description="Explain what a code snippet does. Default output_format=json; pass markdown for freeform.",
    )
) -> Union[ExplainResponse, Answer]:
    if body is None or (not isinstance(body.content, str)) or (len(body.content.strip()) == 0):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="content is empty")
    if len(body.content) > MAX_TA_CHARS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"content exceeds {MAX_TA_CHARS} characters; please trim")
    ta = TextAnalizer()
    content = ta.explain_code(body.content)
    if (body.output_format or "json").lower() == "markdown":
        return Answer(content=content)
    return ExplainResponse(status="ok", explanation=content or "", key_points=[])


@app.post("/knowledge_base/text_analizer/code/debug", response_model=Union[DebugResponse, Answer])
def debug_code(
    body: CodeAnalysisRequest = Body(
        ...,
        example={"content": "def foo(x): return x+1 # bug?", "language": "python", "output_format": "json"},
        description="Debug assistance for a code snippet. Default output_format=json; pass markdown for freeform.",
    )
) -> Union[DebugResponse, Answer]:
    if body is None or (not isinstance(body.content, str)) or (len(body.content.strip()) == 0):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="content is empty")
    if len(body.content) > MAX_TA_CHARS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"content exceeds {MAX_TA_CHARS} characters; please trim")
    ta = TextAnalizer()
    content = ta.debug_code(body.content)
    if (body.output_format or "json").lower() == "markdown":
        return Answer(content=content)
    # Minimal shaping
    issues: List[DebugIssue] = []
    if content:
        issues.append(DebugIssue(title="analysis", rationale=content))
    return DebugResponse(status="ok", issues=issues, test_suggestions=[])


@app.post("/knowledge_base/text_analizer/notes/generate_questions", response_model=Union[QuestionsResponse, Answer])
def generate_questions(
    body: QuestionsRequest = Body(
        ...,
        example={"content": "# Note title\nSome text...", "num_questions": 5, "output_format": "json"},
        description="Generate questions for a note paragraph. Default output_format=json; pass markdown for freeform.",
    )
) -> Union[QuestionsResponse, Answer]:
    if body is None or (not isinstance(body.content, str)) or (len(body.content.strip()) == 0):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="content is empty")
    if len(body.content) > MAX_TA_CHARS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"content exceeds {MAX_TA_CHARS} characters; please trim")
    ta = TextAnalizer()
    content = ta.generate_questions(body.content)
    if (body.output_format or "json").lower() == "markdown":
        return Answer(content=content)
    # Split into lines and keep non-empty as simple list
    lines = [ln.strip() for ln in (content or "").splitlines()]
    questions = [ln for ln in lines if ln]
    # If num_questions is provided, trim
    try:
        n = max(1, min(20, int(body.num_questions or 5)))
    except Exception:
        n = 5
    return QuestionsResponse(status="ok", questions=questions[:n])


@app.post("/knowledge_base/notes/get_for_path")
def get_for_path(
    file: File = Body(
        ...,
        example={"path": "/abs/path/to/vault/Note.md", "type": "Notes"},
        description="Export the subgraph for a single file path inside the vault. Path must be absolute.",
    )
) -> Response:
    mm = MemgraphManager()
    data = mm.export_data_for_file_path(file.path)
    if data:
        json_data = jsonable_encoder(data)
        return JSONResponse(content=json_data)
    else:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

# TODO: test with GPT4


@app.put("/knowledge_base/notes/update_file")
def update_file(
    file: File = Body(
        ..., 
        example={
            "path": "/abs/path/to/vault/Note.md",
            "type": "Notes",
            "content": "# Title\nBody text..."
        },
        description=(
            "Update or replace a note file.\n\n"
            "path: Absolute path inside your vault.\n"
            "type: 'Notes' (optional for this endpoint).\n"
            "content: Full raw text of the note. If omitted, server will try to read from 'path'."
        ),
    )
):
    """Update/replace a note file (delete + add) and refresh embeddings.

    Recommended: Provide 'content' so ingestion doesn't rely on container file mounts.
    """
    try:
        if not os.path.isabs(file.path):
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={
                "status": "error",
                "message": "path must be an absolute path",
                "path": file.path,
            })
        repo_path = Utils.repo_path_from_file_path(file.path)
        vm = VaultManager(repo_path)
        vm.update_file(file.path, file.content)
        return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ok", "path": file.path})
    except Exception as e:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "message": str(e), "path": file.path})

# TODO: test with GPT4


@app.put("/knowledge_base/notes/add_file")
def add_file(
    file: File = Body(
        ..., 
        example={
            "path": "/abs/path/to/vault/New Note.md",
            "type": "Notes",
            "content": "# New Note\n..."
        },
        description=(
            "Add a new note file to the knowledge base.\n\n"
            "path: Absolute path inside your vault.\n"
            "type: 'Notes' (optional for this endpoint).\n"
            "content: Full raw text of the note. If omitted, server will try to read from 'path'."
        ),
    )
):
    """Add a single note file and index it in Memgraph + Chroma."""
    try:
        if not os.path.isabs(file.path):
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={
                "status": "error",
                "message": "path must be an absolute path",
                "path": file.path,
            })
        repo_path = Utils.repo_path_from_file_path(file.path)
        vm = VaultManager(repo_path)
        vm.add_file(file.path, file.content)
        return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ok", "path": file.path})
    except Exception as e:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error", "message": str(e), "path": file.path})


@app.delete("/knowledge_base/notes/delete_file")
def delete_file(
    file: File = Body(
        ...,
        example={"path": "/abs/path/to/vault/Note.md", "type": "Notes"},
        description="Delete a note's graph and vectors. Returns JSON {status:'ok', path} on success. Path must be absolute.",
    )
):
    try:
        if not os.path.isabs(file.path):
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={
                "status": "error",
                "message": "path must be an absolute path",
                "path": file.path,
            })
        repo_path = Utils.repo_path_from_file_path(file.path)
        vm = VaultManager(repo_path)
        vm.delete_file(file.path)
        return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ok", "path": file.path})
    except Exception as e:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={
            "status": "error",
            "message": str(e),
            "path": getattr(file, 'path', None),
        })


@app.post("/knowledge_base/notes/rename_file")
def rename_file(
    old_file: File = Body(
        ..., 
        embed=True,
        example={"path": "/abs/path/to/vault/Old.md", "type": "Notes"},
        description="Old/previous absolute file path in the vault.",
    ),
    new_file: File = Body(
        ..., 
        embed=True,
        example={"path": "/abs/path/to/vault/New.md", "type": "Notes"},
        description="New/target absolute file path in the vault.",
    ),
):
    try:
        repo_path = Utils.repo_path_from_file_path(old_file.path)
        vm = VaultManager(repo_path)
        vm.rename_file(old_file.path, new_file.path)
        return JSONResponse(status_code=status.HTTP_200_OK, content={
            "status": "ok",
            "old_path": old_file.path,
            "new_path": new_file.path,
        })
    except Exception as e:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={
            "status": "error",
            "message": str(e),
            "old_path": getattr(old_file, 'path', None),
            "new_path": getattr(new_file, 'path', None),
        })


@app.post("/knowledge_base/notes/node_to_sentences")
def node_to_sentences(
    node: Node = Body(
        ...,
        example={"repo": {"path": "/abs/path/to/vault", "type": "Notes"}, "id": 123},
        description="Vector search: retrieve top-matching sentences for a graph node ID. Optional query param top_k (default 3).",
    ),
    top_k: int = 3,
) -> List[Sentence]:
    # Input validation for top_k
    try:
        k = int(top_k)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="top_k must be an integer")
    if k < 1 or k > 50:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="top_k must be between 1 and 50")
    searcher = Searcher(node.repo.path)
    return [Sentence(repo=node.repo, content=c) for c in searcher.node_id_to_sentences(node.id, top_k=k)]


@app.post("/knowledge_base/notes/sentence_to_nodes")
def sentence_to_nodes(
    sentence: Sentence = Body(
        ...,
        example={"repo": {"path": "/abs/path/to/vault", "type": "Notes"}, "content": "some sentence"},
        description="Vector search: find node IDs most similar to a sentence. Optional query param top_k (default 1).",
    ),
    top_k: int = 1,
) -> List[Node]:
    # Input validation for top_k
    try:
        k = int(top_k)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="top_k must be an integer")
    if k < 1 or k > 50:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="top_k must be between 1 and 50")
    searcher = Searcher(sentence.repo.path)
    return [Node(repo=sentence.repo, id=i) for i in searcher.sentence_to_node_ids(sentence.content, top_k=k)]


@app.post("/knowledge_base/notes/suggest_link")
def suggest_link(
    sentence: Sentence = Body(
        ...,
        example={"repo": {"path": "/abs/path/to/vault", "type": "Notes"}, "content": "snippet of text"},
        description="Heuristic: suggest the most probable file path(s) for a given text snippet. Optional query param top_k (default 1).",
    ),
    top_k: int = 1,
):
    # Input validation for top_k
    try:
        k = int(top_k)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="top_k must be an integer")
    if k < 1 or k > 50:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="top_k must be between 1 and 50")
    searcher = Searcher(sentence.repo.path)
    if k == 1:
        return File(path=searcher.most_probable_filename_for_text(query_text=sentence.content), type=Type.NOTES, content=None)
    candidates = searcher.most_probable_filenames_for_text(query_text=sentence.content, top_k=k)
    # Return a simple JSON payload for multiple candidates
    return JSONResponse(status_code=status.HTTP_200_OK, content={
        "status": "ok",
        "candidates": candidates,
    })


@app.post("/knowledge_base/code/init_repo_from_api")
def init_repo_from_api(
    remote_repo: RemoteRepo = Body(
        ...,
        example={"owner": "org", "repo": "name", "ref": "main"},
        description=(
            "Initialize a code repo by fetching the directory tree from GitHub's contents API and "
            "emitting a Repo/Dir/File graph (CONTAINS relationships). Optional: ref (branch/tag) and token for auth."
        ),
    )
) -> JSONResponse:
    try:
        mm = MemgraphManager()
        arm = APIRepoManager(remote_repo.owner, remote_repo.repo, token=remote_repo.token, ref=remote_repo.ref)
        cypher = arm.generate_cypher()
        # Basic stats
        creates = cypher.count("CREATE (")
        merges = cypher.count("MERGE (")
        mm.run_update_query(cypher)
        return JSONResponse(status_code=status.HTTP_200_OK, content={
            "status": "ok",
            "owner": remote_repo.owner,
            "repo": remote_repo.repo,
            "ref": remote_repo.ref or "default",
            "nodes_created": creates,
            "relationships_created": merges,
        })
    except Exception as e:
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={
            "status": "error",
            "message": str(e),
            "owner": remote_repo.owner,
            "repo": remote_repo.repo,
            "ref": remote_repo.ref or "default",
        })


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "app://obsidian.md",
        "http://localhost:*",
        "http://127.0.0.1:*",
        "https://localhost:*",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
