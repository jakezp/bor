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

        chroma_data_dir = constants.CHROMA_DATA_DIR or "./data/chroma"
        self.chroma_client = chromadb.PersistentClient(path=chroma_data_dir)
        
        # We'll handle embeddings manually using our Bedrock implementation
        self.ada_ef = None

        if repo_path is not None:
            self.collection_name = Utils.collection_name_from_repo_path(
                repo_path)
            self._make_collection(self.collection_name)

        return

    def _make_collection(self, collection_name: str) -> None:
        self.collection = self.chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": constants.CHROMA_VECTOR_SPACE}
        )
        return

    def _delete_collection(self, collection_name: str) -> None:
        self.chroma_client.delete_collection(name=collection_name)
        return

    def delete_all(self) -> None:
        self.chroma_client.reset()
        return

    def add_file(self, file_path: Union[str, os.PathLike]) -> None:
        text = pathlib.Path(file_path).read_text()
        sentences = nltk.tokenize.sent_tokenize(text)
        text_len = len(sentences)
        sent_ids = [f"{file_path}_{str(ind)}" for ind in range(text_len)]
        metadatas = [{"file_path": str(file_path)} for _ in range(text_len)]
        self.collection.add(
            documents=sentences,
            metadatas=metadatas,
            ids=sent_ids
        )
        return

    def delete_file(self, file_path: Union[str, os.PathLike]) -> None:
        self.collection.delete(
            where={"file_path": str(file_path)}
        )
        return

    def rename_file(self, old_file_path: Union[str, os.PathLike], new_file_path: Union[str, os.PathLike]) -> None:
        result = self.collection.get(where={"file_path": str(old_file_path)})
        ids = result['ids']
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
