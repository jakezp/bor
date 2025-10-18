from typing import List

import os
import glob

ALLOWED_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")


class Utils:
    @staticmethod
    def collection_name_from_repo_path(repo_path: str) -> str:
        """Return a Chroma-safe collection name derived from repo_path.

        Rules (Chroma): 3-512 chars; [a-zA-Z0-9._-]; must start and end with [a-zA-Z0-9].
        We sanitize and provide a stable fallback when inputs are empty/relative.
        """
        base = os.path.basename(os.path.normpath(repo_path)) if repo_path else ""
        if not base or base in (".", ".."):
            base = "notes"
        name = Utils._sanitize_collection_name(base)
        return name

    @staticmethod
    def _sanitize_collection_name(name: str) -> str:
        # Replace disallowed characters with '-'
        cleaned = ''.join(ch if ch in ALLOWED_CHARS else '-' for ch in name)
        # Trim leading/trailing non-alphanumeric
        def is_alnum(c: str) -> bool:
            return ('a' <= c <= 'z') or ('A' <= c <= 'Z') or ('0' <= c <= '9')
        while cleaned and not is_alnum(cleaned[0]):
            cleaned = cleaned[1:]
        while cleaned and not is_alnum(cleaned[-1]):
            cleaned = cleaned[:-1]
        if not cleaned:
            cleaned = "notes"
        # Enforce length 3..512
        if len(cleaned) < 3:
            cleaned = (cleaned + "xxx")[:3]
        if len(cleaned) > 512:
            cleaned = cleaned[:512]
        return cleaned

    @staticmethod
    def repo_path_from_file_path(file_path: str) -> str:
        return os.path.dirname(file_path)

    @staticmethod
    def collection_name_from_file_path(file_path: str) -> str:
        return Utils.collection_name_from_repo_path(Utils.repo_path_from_file_path(file_path))

    @staticmethod
    def get_all_files_recursive(path_to_root: str) -> List[str]:
        search_path = os.path.join(path_to_root, '**', '*')
        return [os.path.abspath(f) for f in glob.glob(search_path, recursive=True) if os.path.isfile(f)]

    @staticmethod
    def edge_to_dict(edge):
        return {
            "id": edge.id,
            "start": edge.start_id,
            "end": edge.end_id,
            "label": edge.type,
            "properties": edge.properties,
            "type": type(edge).__name__.lower(),
        }

    @staticmethod
    def node_to_dict(node):
        return {
            "id": node.id,
            "labels": list(node.labels),
            "properties": node.properties,
            "type": type(node).__name__.lower(),
        }

    @staticmethod
    def results_to_dictlist(results, return_name):
        rows = list(results)
        flat_nodes = []
        flat_edges = []
        for row in rows:
            subgraph = row.get(return_name) if isinstance(row, dict) else row[return_name]
            if not subgraph:
                continue
            nodes = subgraph.get('nodes') if isinstance(subgraph, dict) else getattr(subgraph, 'nodes', None)
            edges = subgraph.get('edges') if isinstance(subgraph, dict) else getattr(subgraph, 'edges', None)
            # Some Memgraph drivers return objects; fall back to attribute access
            iter_nodes = nodes if isinstance(nodes, list) else (list(nodes) if nodes is not None else [])
            iter_edges = edges if isinstance(edges, list) else (list(edges) if edges is not None else [])
            flat_nodes.extend([Utils.node_to_dict(n) for n in iter_nodes])
            flat_edges.extend([Utils.edge_to_dict(e) for e in iter_edges])
        return flat_nodes + flat_edges
