from __future__ import annotations

from typing import List, Optional
import os
import concurrent.futures as _fut
import json
import hashlib
import threading
import pathlib

from core.knowledgebase import constants
from core.knowledgebase.AWSAuth import AWSAuthenticator

# Cache Bedrock runtime client to avoid re-auth and duplicate logs per call
_authenticator = AWSAuthenticator()
_bedrock_runtime_client = None
_cache_lock = threading.Lock()


def _cache_dir() -> str:
    base = os.environ.get("EMBEDDING_CACHE_DIR") or os.path.join((constants.CHROMA_DATA_DIR or "."), "emb_cache")
    pathlib.Path(base).mkdir(parents=True, exist_ok=True)
    return base


def _hash_text(text: str, model: str) -> str:
    h = hashlib.sha256()
    h.update((model + "\n" + text).encode("utf-8"))
    return h.hexdigest()


def _cache_path(key: str) -> str:
    return os.path.join(_cache_dir(), key + ".json")


def _cache_get(key: str) -> Optional[List[float]]:
    if os.environ.get("EMBEDDING_CACHE_ENABLE", "true").lower() not in ("1", "true", "yes", "on"):
        return None
    path = _cache_path(key)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            return data.get("embedding")
    except Exception:
        return None


def _cache_put(key: str, embedding: List[float]) -> None:
    if os.environ.get("EMBEDDING_CACHE_ENABLE", "true").lower() not in ("1", "true", "yes", "on"):
        return
    path = _cache_path(key)
    tmp = path + ".tmp"
    with _cache_lock:
        try:
            with open(tmp, "w") as f:
                json.dump(embedding, f)
            os.replace(tmp, path)
        except Exception:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass


class Embeddings:
    @staticmethod
    def get_embedding(text: str, model=constants.BEDROCK_EMBEDDING_MODEL) -> List[float]:
        """Get embeddings using AWS Bedrock embedding model."""
        text = text.replace("\n", " ")
        cache_key = _hash_text(text, model)
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached
        
        # Get authenticated Bedrock runtime client (cached)
        global _bedrock_runtime_client
        if _bedrock_runtime_client is None:
            _bedrock_runtime_client = _authenticator.get_bedrock_runtime_client()
        bedrock_runtime = _bedrock_runtime_client
        
        # Prepare the request body for Bedrock embedding
        request_body = {
            "inputText": text
        }
        
        try:
            # Call Bedrock embedding API
            response = bedrock_runtime.invoke_model(
                modelId=model,
                body=json.dumps(request_body),
                contentType='application/json',
                accept='application/json'
            )
            
            # Parse the response
            response_body = json.loads(response['body'].read())
            
            # Extract embedding vector (format depends on the embedding model)
            if 'embedding' in response_body:
                emb = response_body['embedding']
                _cache_put(cache_key, emb)
                return emb
            elif 'embeddings' in response_body:
                emb = response_body['embeddings'][0]  # Assuming first embedding
                _cache_put(cache_key, emb)
                return emb
            else:
                raise ValueError(f"Unexpected response format: {response_body}")
                
        except Exception as e:
            raise RuntimeError(f"Failed to get embeddings from Bedrock: {e}")

    @staticmethod
    def get_embeddings(texts: List[str], model=constants.BEDROCK_EMBEDDING_MODEL) -> List[List[float]]:
        """Batch embed a list of texts.

        - Uses a shared Bedrock runtime client
        - Simple concurrency via ThreadPoolExecutor (configurable via EMBEDDING_BATCH_WORKERS)
        - Preserves input order
        """
        if not texts:
            return []

        # Clean texts
        cleaned = [t.replace("\n", " ") if isinstance(t, str) else "" for t in texts]

        # Get authenticated Bedrock runtime client (cached)
        global _bedrock_runtime_client
        if _bedrock_runtime_client is None:
            _bedrock_runtime_client = _authenticator.get_bedrock_runtime_client()
        bedrock_runtime = _bedrock_runtime_client

        # Titan v2 expects single inputText per call, so we parallelize calls
        workers = int(os.environ.get("EMBEDDING_BATCH_WORKERS", "4"))
        group_size = int(os.environ.get("EMBEDDING_GROUP_SIZE", "1"))  # reserved for future multi-input models

        def _embed_one(text: str) -> List[float]:
            ckey = _hash_text(text, model)
            cval = _cache_get(ckey)
            if cval is not None:
                return cval
            request_body = {"inputText": text}
            response = bedrock_runtime.invoke_model(
                modelId=model,
                body=json.dumps(request_body),
                contentType='application/json',
                accept='application/json'
            )
            response_body = json.loads(response['body'].read())
            if 'embedding' in response_body:
                emb = response_body['embedding']
                _cache_put(ckey, emb)
                return emb
            elif 'embeddings' in response_body:
                emb = response_body['embeddings'][0]
                _cache_put(ckey, emb)
                return emb
            else:
                raise ValueError(f"Unexpected response format: {response_body}")

        if workers <= 1 or len(cleaned) == 1:
            return [_embed_one(t) for t in cleaned]

        results: List[List[float]] = [None] * len(cleaned)  # type: ignore
        with _fut.ThreadPoolExecutor(max_workers=workers) as ex:
            future_map = {ex.submit(_embed_one, t): i for i, t in enumerate(cleaned)}
            for fut in _fut.as_completed(future_map):
                i = future_map[fut]
                try:
                    results[i] = fut.result()
                except Exception as e:
                    raise RuntimeError(f"Failed to get embedding for index {i}: {e}")

        # type: ignore is safe here because we fill every slot or raise
        return results  # type: ignore


if __name__ == '__main__':
    print(Embeddings.get_embedding('bonaparte'))
