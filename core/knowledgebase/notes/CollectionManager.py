from __future__ import annotations

from typing import Union, Optional, Dict, Any, List

import pathlib
import os

import chromadb
import nltk

import core.knowledgebase.constants as constants
from core.knowledgebase.Utils import Utils
from core.knowledgebase.notes.Embeddings import Embeddings


class CollectionManager:
    def __init__(self, repo_path: Optional[str] = None) -> None:

        # Ensure required NLTK resources are available at runtime
        self._ensure_nltk_resources()

        chroma_data_dir = constants.CHROMA_DATA_DIR or "./data/chroma"
        self.chroma_client = chromadb.PersistentClient(path=chroma_data_dir)
        
        # We'll handle embeddings manually using our Bedrock implementation
        self.ada_ef = None

        if repo_path is not None:
            safe_name = Utils.collection_name_from_repo_path(repo_path)
            self.collection_name = safe_name
            self._make_collection(self.collection_name)

        return

    def _ensure_nltk_resources(self) -> None:
        """Ensure NLTK tokenizers used by sent_tokenize are available.

        Newer NLTK versions may require both 'punkt' and 'punkt_tab'. We'll
        try to locate them and download quietly if missing. If downloads fail,
        we surface a clear error message.
        """
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            try:
                nltk.download('punkt', quiet=True)
            except Exception as e:
                raise RuntimeError(f"Failed to download NLTK resource 'punkt': {e}")

        # Some NLTK versions use an auxiliary 'punkt_tab' package. Attempt to ensure it.
        try:
            nltk.data.find('tokenizers/punkt_tab')
        except LookupError:
            try:
                nltk.download('punkt_tab', quiet=True)
            except Exception:
                # If this package doesn't exist in this NLTK version or download fails,
                # proceed; sent_tokenize typically works with 'punkt' alone.
                pass

    def _make_collection(self, collection_name: str) -> None:
        # Important: disable Chroma's default embedding function (which would
        # download ONNX models in the container). We'll manage embeddings via
        # our Bedrock Embeddings implementation and pass vectors explicitly.
        self.collection = self.chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": constants.CHROMA_VECTOR_SPACE},
            embedding_function=None,
        )
        return

    def _delete_collection(self, collection_name: str) -> None:
        self.chroma_client.delete_collection(name=collection_name)
        return

    def delete_all(self) -> None:
        # Some Chroma deployments disable reset(). Prefer enumerating
        # and deleting collections to avoid 'Reset is disabled by config'.
        try:
            collections = self.chroma_client.list_collections()
            for col in collections:
                try:
                    # col can be a Collection object or metadata dict depending on version
                    name = getattr(col, 'name', None) or (col.get('name') if isinstance(col, dict) else None)
                    if name:
                        self.chroma_client.delete_collection(name=name)
                except Exception:
                    # Continue deleting others even if one fails
                    pass
        except Exception:
            # As a last resort, attempt reset; may be disabled.
            try:
                self.chroma_client.reset()
            except Exception:
                # Ignore if not allowed; caller is clearing Memgraph too
                pass
        return

    def add_file(self, file_path: Union[str, os.PathLike], file_text: Optional[str] = None) -> None:
        # Prefer provided text to avoid relying on container filesystem mounts
        text = file_text if file_text is not None else pathlib.Path(file_path).read_text()
        sentences = nltk.tokenize.sent_tokenize(text)
        text_len = len(sentences)
        sent_ids = [f"{file_path}_{str(ind)}" for ind in range(text_len)]
        metadatas = [{"file_path": str(file_path)} for _ in range(text_len)]
        # Compute embeddings via Bedrock (explicitly) to avoid Chroma's
        # default ONNX model download path.
        try:
            embeddings = Embeddings.get_embeddings(sentences)
        except Exception as e:
            raise RuntimeError(f"Failed to embed sentences for {file_path}: {e}")

        self.collection.add(
            documents=sentences,
            metadatas=metadatas,
            ids=sent_ids,
            embeddings=embeddings,
        )
        return

    def delete_file(self, file_path: Union[str, os.PathLike]) -> None:
        self.collection.delete(
            where={"file_path": str(file_path)}
        )
        return

    def rename_file(self, old_file_path: Union[str, os.PathLike], new_file_path: Union[str, os.PathLike]) -> None:
        result = self.collection.get(where={"file_path": str(old_file_path)})
        ids = result.get('ids', [])
        if not ids:
            # Nothing to rename in the vector store; treat as no-op
            return
        metadatas = [{"file_path": str(new_file_path)} for _ in range(len(ids))]
        self.collection.update(ids=ids, metadatas=metadatas)
        return

    def delete_all_from_collection(self) -> None:
        self._delete_collection(self.collection_name)
        self._make_collection(self.collection_name)
        return


if __name__ == '__main__':

    example_reponame = 'History'
    example_repopath = os.path.join(os.path.dirname(
        __file__), '..', 'examples', example_reponame)

    example_fname = 'napoleon.txt'
    example_fpath = os.path.join(example_repopath, example_fname)

    cm = CollectionManager(example_repopath)
    cm.delete_all_from_collection()
    cm.add_file(example_fpath)

    print(cm.collection.query(query_texts="napoleon"))
