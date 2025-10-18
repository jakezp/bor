from __future__ import annotations

from typing import List, Optional, Any
import uuid

import os

from core.knowledgebase.notes.Embeddings import Embeddings
from core.knowledgebase.MemgraphManager import MemgraphManager
from core.knowledgebase.notes.CollectionManager import CollectionManager


class Searcher:
    def __init__(self: Searcher, repo_path: str) -> None:
        self.repo_path = repo_path
        self.mm = MemgraphManager()
        return

    def search_graph(self: Searcher, query_text: Optional[str] = None, query_embeddings: Optional[List[float]] = None, limit: int = 3) -> List[Any]:
        assert (query_text is not None) or (query_embeddings is not None)
        if query_text is not None:
            emb_vector = Embeddings.get_embedding(query_text)
        else:
            emb_vector = query_embeddings

        assert emb_vector is not None, "search_graph requires embeddings"
        req = str(uuid.uuid4())
        self.mm.create_temp_nodes(emb_vector, req=req)
        results = None
        try:
            results = self.mm.vector_search_query(limit=max(1, int(limit)), req=req)
        finally:
            self.mm.delete_temp_nodes(req=req)
        return list(results)

    def search_graph_tool(self: Searcher, query: str) -> str:
        results = self.search_graph(query_text=query)
        out = ""
        for res in results:
            out += self.mm.describe_node(res['ID(node1)'])
            out += "-------------\n"
        return out

    def search_text(self: Searcher, query_text: Optional[str] = None, query_embeddings: Optional[List[float]] = None, n_results: int = 3) -> List[str]:
        cm = CollectionManager(self.repo_path)
        # If query_text is provided but no embeddings, compute via Bedrock to
        # avoid Chroma's internal ONNX embedding function.
        if query_embeddings is None and query_text is not None:
            query_embeddings = Embeddings.get_embedding(query_text)

        res = cm.collection.query(
            query_texts=None,  # ensure Chroma doesn't attempt to embed
            query_embeddings=[query_embeddings] if isinstance(query_embeddings, list) else query_embeddings,
            n_results=max(1, int(n_results)),
        )
        return res['documents'][0]

    def search_text_tool(self: Searcher, query: str) -> str:
        return '\n'.join(self.search_text(query_text=query))

    def node_id_to_sentences(self: Searcher, id: int, top_k: int = 3) -> List[str]:
        emb = self.mm.embeddings_for_node(id)
        return self.search_text(query_embeddings=emb, n_results=top_k)

    def sentence_to_node_ids(self: Searcher, sentence: str, top_k: int = 1) -> List[int]:
        cm = CollectionManager(self.repo_path)
        sent_emb = Embeddings.get_embedding(sentence)
        res = cm.collection.query(
            query_texts=None,
            query_embeddings=[sent_emb],
            n_results=max(1, int(top_k)),
            include=['embeddings']
        )
        # Use the stored document embeddings to search in the graph
        emb = res['embeddings'][0][0]
        return [node['ID(node1)'] for node in self.search_graph(query_embeddings=emb, limit=max(1, int(top_k)))]

    def most_probable_filename_for_text(self: Searcher, query_text: Optional[str] = None) -> str:
        cm = CollectionManager(self.repo_path)
        query_emb = Embeddings.get_embedding(query_text) if query_text is not None else None
        res = cm.collection.query(
            query_texts=None,
            query_embeddings=[query_emb] if isinstance(query_emb, list) else query_emb,
            n_results=1
        )
        fname = res['metadatas'][0][0]['file_path']
        return fname

    def most_probable_filenames_for_text(self: Searcher, query_text: Optional[str] = None, top_k: int = 1) -> List[str]:
        cm = CollectionManager(self.repo_path)
        query_emb = Embeddings.get_embedding(query_text) if query_text is not None else None
        res = cm.collection.query(
            query_texts=None,
            query_embeddings=[query_emb] if isinstance(query_emb, list) else query_emb,
            n_results=max(1, int(top_k))
        )
        metadatas = res.get('metadatas', [[]])[0]
        raw_paths = [m.get('file_path') for m in metadatas if isinstance(m, dict)]
        paths = [str(p) for p in raw_paths if p is not None]
        # Deduplicate while preserving order
        seen = set()
        uniq_paths: List[str] = []
        for p in paths:
            if p not in seen:
                seen.add(p)
                uniq_paths.append(p)
        return uniq_paths[:max(1, int(top_k))]


if __name__ == '__main__':
    query_text = "counsul"
    example_reponame = 'History'
    example_repopath = os.path.join(os.path.dirname(
        __file__), '..', 'examples', example_reponame)
    searcher = Searcher(example_reponame)

    print(searcher.search_graph(query_text=query_text))
    print(searcher.search_text(query_text=query_text))
    print(searcher.most_probable_filename_for_text(query_text))
    print(searcher.node_id_to_sentences(
        searcher.sentence_to_node_ids('Napoleon bonaparte was born')[0]))
