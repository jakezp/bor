from __future__ import annotations
from typing import Optional, Dict, List, Any, Iterator

import json
import os
from pathlib import Path
import re
import logging

from gqlalchemy import Memgraph

from core.knowledgebase import constants
from core.knowledgebase.Utils import Utils
from core.knowledgebase.CypherQueryHandler import CypherQueryHandler as CQ
from core.knowledgebase.notes.Embeddings import Embeddings

logger = logging.getLogger(__name__)


class MemgraphManager:
    def __init__(self: MemgraphManager) -> None:
        self.db = Memgraph(host=constants.MEMGRAPH_HOST,
                           port=constants.MEMGRAPH_PORT)
        return

    @staticmethod
    def _row_get(row: Any, *keys: str):
        """Return value from a query row trying keys in order; if not found, return the first value if row is a dict."""
        try:
            if isinstance(row, dict):
                for k in keys:
                    if k in row:
                        return row[k]
                # fallback: first value
                for _, v in row.items():
                    return v
        except Exception:
            pass
        # Try mapping access on non-dict
        for k in keys:
            try:
                return row[k]
            except Exception:
                try:
                    return getattr(row, k)
                except Exception:
                    continue
        return None

    def run_update_query(self, query: str) -> None:
        """Execute potentially multi-statement Cypher safely, one statement at a time.

        - Strips accidental Markdown code fences
        - Splits on semicolons
        - Executes each statement individually
        - Logs (and continues) on errors so a single bad statement doesn't halt ingestion
        """
        if not query or not query.strip():
            return

        clean = query.strip()

        # Remove surrounding Markdown code fences if present
        if clean.startswith("```"):
            # Drop opening fence like ``` or ```cypher
            clean = re.sub(r"^```[a-zA-Z]*\s*\n?", "", clean)
            # Drop trailing fence
            clean = re.sub(r"\n?```$", "", clean)

        # Split by semicolons; keep only non-empty statements
        statements = [s.strip() for s in clean.split(';') if s.strip()]

        for stmt in statements:
            # Soft guardrail: warn on unlabeled node patterns like CREATE (n {..}) or MERGE (n {..})
            try:
                unlabeled_pattern = re.compile(r"\b(CREATE|MERGE)\s*\(\s*[a-zA-Z_][a-zA-Z0-9_]*\s*\{", re.IGNORECASE)
                labeled_pattern = re.compile(r"\b(CREATE|MERGE)\s*\(\s*:[A-Za-z][A-Za-z0-9_]*", re.IGNORECASE)
                if unlabeled_pattern.search(stmt) and not labeled_pattern.search(stmt):
                    logger.warning("Detected potential unlabeled node statement; consider adding a label or :Unknown. Statement: %s", stmt)
            except Exception:
                pass
            try:
                self.db.execute(stmt)
            except Exception as e:
                logger.error(
                    "Error running update query statement:\n%s\nError: %s", stmt, str(e)
                )
        return

    def run_select_query(self: MemgraphManager, query: str) -> Iterator[Dict[str, Any]]:
        res = self.db.execute_and_fetch(query)
        return res

    @staticmethod
    def select_query_tool(query: str) -> List[Any]:
        return list(MemgraphManager().run_select_query(query))

    def check_if_db_empty(self: MemgraphManager) -> bool:
        query = CQ.get_check_if_db_empty_query()
        res = self.run_select_query(query)
        res = next(res)
        return int(res['nodes']) == 0

    def export_data_for_repo_path(self: MemgraphManager, repo_path: str) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        # Nodes: export as plain dicts
        try:
            node_rows = self.db.execute_and_fetch(
                (
                    "MATCH (n) WHERE n.repo_path = '" + repo_path + "' "
                    "RETURN id(n) AS id, labels(n) AS labels, properties(n) AS properties"
                )
            )
            for row in node_rows:
                try:
                    # gqlalchemy returns dict-like rows
                    items.append({
                        "id": row.get("id") if isinstance(row, dict) else row["id"],
                        "labels": row.get("labels") if isinstance(row, dict) else row["labels"],
                        "properties": row.get("properties") if isinstance(row, dict) else row["properties"],
                        "type": "node",
                    })
                except Exception as e:
                    logger.error("export_data_for_repo_path node row error: %s", str(e))
        except Exception as e:
            logger.error("export_data_for_repo_path nodes error: %s", str(e))
        # Relationships: export as plain dicts including endpoints
        try:
            rel_rows = self.db.execute_and_fetch(
                (
                    "MATCH (a)-[r]->(b) WHERE r.repo_path = '" + repo_path + "' "
                    "RETURN id(r) AS id, id(a) AS start, id(b) AS end, type(r) AS label, properties(r) AS properties"
                )
            )
            for row in rel_rows:
                try:
                    items.append({
                        "id": row.get("id") if isinstance(row, dict) else row["id"],
                        "start": row.get("start") if isinstance(row, dict) else row["start"],
                        "end": row.get("end") if isinstance(row, dict) else row["end"],
                        "label": row.get("label") if isinstance(row, dict) else row["label"],
                        "properties": row.get("properties") if isinstance(row, dict) else row["properties"],
                        "type": "edge",
                    })
                except Exception as e:
                    logger.error("export_data_for_repo_path rel row error: %s", str(e))
        except Exception as e:
            logger.error("export_data_for_repo_path rels error: %s", str(e))
        # Fallback: if items unexpectedly empty but data exists, return object-based results
        if not items:
            try:
                # Try object-based nodes
                node_rows = self.db.execute_and_fetch(
                    f"MATCH (n) WHERE n.repo_path = '{repo_path}' RETURN n AS n"
                )
                for row in node_rows:
                    try:
                        nobj = self._row_get(row, 'n', 'node')
                        if nobj is not None:
                            items.append(Utils.node_to_dict(nobj))
                    except Exception:
                        continue
                # Try object-based relationships
                rel_rows = self.db.execute_and_fetch(
                    f"MATCH ()-[r]->() WHERE r.repo_path = '{repo_path}' RETURN r AS r"
                )
                for row in rel_rows:
                    try:
                        robj = self._row_get(row, 'r', 'rel')
                        if robj is not None:
                            items.append(Utils.edge_to_dict(robj))
                    except Exception:
                        continue
            except Exception:
                pass
        return items

    def export_data_for_file_path(self: MemgraphManager, file_path: str) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        # Nodes for file
        try:
            node_rows = self.db.execute_and_fetch(
                (
                    "MATCH (n) WHERE n.file_path = '" + file_path + "' "
                    "RETURN id(n) AS id, labels(n) AS labels, properties(n) AS properties"
                )
            )
            for row in node_rows:
                try:
                    items.append({
                        "id": row.get("id") if isinstance(row, dict) else row["id"],
                        "labels": row.get("labels") if isinstance(row, dict) else row["labels"],
                        "properties": row.get("properties") if isinstance(row, dict) else row["properties"],
                        "type": "node",
                    })
                except Exception as e:
                    logger.error("export_data_for_file_path node row error: %s", str(e))
        except Exception as e:
            logger.error("export_data_for_file_path nodes error: %s", str(e))
        # Relationships for file
        try:
            rel_rows = self.db.execute_and_fetch(
                (
                    "MATCH (a)-[r]->(b) WHERE r.file_path = '" + file_path + "' "
                    "RETURN id(r) AS id, id(a) AS start, id(b) AS end, type(r) AS label, properties(r) AS properties"
                )
            )
            for row in rel_rows:
                try:
                    items.append({
                        "id": row.get("id") if isinstance(row, dict) else row["id"],
                        "start": row.get("start") if isinstance(row, dict) else row["start"],
                        "end": row.get("end") if isinstance(row, dict) else row["end"],
                        "label": row.get("label") if isinstance(row, dict) else row["label"],
                        "properties": row.get("properties") if isinstance(row, dict) else row["properties"],
                        "type": "edge",
                    })
                except Exception as e:
                    logger.error("export_data_for_file_path rel row error: %s", str(e))
        except Exception as e:
            logger.error("export_data_for_file_path rels error: %s", str(e))
        # Fallback
        if not items:
            try:
                node_rows = self.db.execute_and_fetch(
                    f"MATCH (n) WHERE n.file_path = '{file_path}' RETURN n AS n"
                )
                for row in node_rows:
                    try:
                        nobj = self._row_get(row, 'n', 'node')
                        if nobj is not None:
                            items.append(Utils.node_to_dict(nobj))
                    except Exception:
                        continue
                rel_rows = self.db.execute_and_fetch(
                    f"MATCH ()-[r]->() WHERE r.file_path = '{file_path}' RETURN r AS r"
                )
                for row in rel_rows:
                    try:
                        robj = self._row_get(row, 'r', 'rel')
                        if robj is not None:
                            items.append(Utils.edge_to_dict(robj))
                    except Exception:
                        continue
            except Exception:
                pass
        return items

    def delete_all(self: MemgraphManager) -> None:
        query = CQ.get_delete_all_query()
        self.db.execute(query)
        return

    def delete_all_for_repo(self: MemgraphManager, repo_path: str) -> None:
        query = CQ.get_delete_all_for_repo_query(repo_path)
        self.db.execute(query)
        return

    def delete_graph_for_file(self: MemgraphManager, file_path: str) -> None:
        query = CQ.get_delete_graph_for_file_query(file_path)
        self.db.execute(query)
        return

    def rename_file(self: MemgraphManager, old_file_path: str, new_file_path: str) -> None:
        # Update node file_path
        query_nodes = CQ.get_rename_file_query(old_file_path, new_file_path)
        self.db.execute(query_nodes)
        # Update relationship file_path for consistency
        try:
            query_rels = CQ.get_rename_relationships_query(old_file_path, new_file_path)
            self.db.execute(query_rels)
        except Exception:
            # Backward compatibility if query helper not available
            self.db.execute(
                f"MATCH ()-[r]->() WHERE r.file_path = '{old_file_path}' SET r.file_path = '{new_file_path}'"
            )
        return

    @staticmethod
    def print_type_and_obj(type: str, obj: Optional[str]) -> str:
        if obj is None:
            return f"{type}"
        return f"{type}: {obj}"

    def describe_node(self: MemgraphManager, id: int) -> str:
        query = CQ.get_node_description_query(id)
        results = self.db.execute_and_fetch(query)
        res = next(results)
        out = ""
        _, node_type, node_name = res['Node_ID'], res['Node_Type'], res['Node_Name']
        out += f"{MemgraphManager.print_type_and_obj(node_type, node_name)}\n"
        for conn in res['In_Connections']:
            rel_type = conn['Relationship_Type']
            if rel_type is None:
                continue
            neighbour_type, neighbour_name = conn['Neighbour_Type'], conn['Neighbour_Name']
            out += f"{MemgraphManager.print_type_and_obj(node_type, node_name)} "
            out += f"{rel_type} "
            out += f"{MemgraphManager.print_type_and_obj(neighbour_type, neighbour_name)}\n"
        for conn in res['Out_Connections']:
            rel_type = conn['Relationship_Type']
            if rel_type is None:
                continue
            neighbour_type, neighbour_name = conn['Neighbour_Type'], conn['Neighbour_Name']
            out += f"{MemgraphManager.print_type_and_obj(neighbour_type, neighbour_name)} "
            out += f"{rel_type} "
            out += f"{MemgraphManager.print_type_and_obj(node_type, node_name)}\n"
        return out

    def strings_to_embed_by_id(self: MemgraphManager, file_path: str) -> Dict[str, str]:
        strings_by_id = dict()
        query = CQ.get_strings_to_embed_query(file_path)
        results = self.db.execute_and_fetch(query)
        for res in results:
            out = ""
            node_id, node_type, node_name = res['Node_ID'], res['Node_Type'], res['Node_Name']
            out += f"{MemgraphManager.print_type_and_obj(node_type, node_name)}\n"
            for conn in res['Connections']:
                rel_type = conn['Relationship_Type']
                if rel_type is None:
                    continue
                neighbour_type, neighbour_name = conn['Neighbour_Type'], conn['Neighbour_Name']
                out += f"{MemgraphManager.print_type_and_obj(node_type, node_name)} "
                out += f"{rel_type} "
                out += f"{MemgraphManager.print_type_and_obj(neighbour_type, neighbour_name)}\n"
            strings_by_id[node_id] = out
        return strings_by_id

    def embeddings_by_id(self: MemgraphManager, file_path: str) -> Dict[str, List[float]]:
        strings_by_id = self.strings_to_embed_by_id(file_path)
        return {id: Embeddings.get_embedding(strings_by_id[id]) for id in strings_by_id.keys()}

    def update_embeddings(self: MemgraphManager, file_path: str) -> None:
        emb_by_id = self.embeddings_by_id(file_path)
        for id in emb_by_id.keys():
            emb = emb_by_id[id]
            query = CQ.get_set_embeddings_query(id, emb)
            self.db.execute(query)
        return

    def create_temp_nodes(self: MemgraphManager, emb_vector: List[float], req: str) -> None:
        # Ensure vector is a plain Python list (not numpy array)
        try:
            if hasattr(emb_vector, 'tolist'):
                emb_vector = emb_vector.tolist()  # type: ignore
        except Exception:
            pass
        query = CQ.get_tmp_create_query()
        # Execute with parameters to avoid Cypher parsing errors
        self.db.execute(query, parameters={"embeddings": emb_vector, "req": req})
        return

    def delete_temp_nodes(self: MemgraphManager, req: str) -> None:
        query = CQ.get_tmp_delete_query()
        self.db.execute(query, parameters={"req": req})
        return

    def get_schema_for_repo(self: MemgraphManager, repo_path: str) -> str:
        query = CQ.get_schema_for_repo_query(repo_path)
        # print(query)
        res = self.db.execute_and_fetch(query)
        return next(res)['schema']

    def vector_search_query(self: MemgraphManager, limit: int = 3, req: str = "") -> List[Any]:
        query = CQ.get_vector_search_query(limit)
        res = self.db.execute_and_fetch(query, parameters={"req": req})
        return list(res)

    def embeddings_for_node(self: MemgraphManager, node_id: int) -> List[float]:
        query = CQ.get_embeddings_for_node_query(node_id)
        res = self.db.execute_and_fetch(query)
        return next(res)['embeddings']

    def normalize_after_ingest(self: MemgraphManager, file_path: str, repo_path: str) -> None:
        """Normalize graph invariants after LLM-generated updates.

        - Ensure all nodes have at least one label; add :Unknown to unlabeled nodes
        - Ensure file_path and repo_path exist on nodes/relationships; set when NULL
          Only fills NULLs; never overwrites existing values.
        """
        # Add fallback label for unlabeled nodes
        self.db.execute("MATCH (n) WHERE size(labels(n)) = 0 SET n:Unknown")
        # Backfill missing file_path/repo_path for nodes
        self.db.execute(
            f"MATCH (n) WHERE n.file_path IS NULL SET n.file_path = '{file_path}'"
        )
        self.db.execute(
            f"MATCH (n) WHERE n.repo_path IS NULL SET n.repo_path = '{repo_path}'"
        )
        # Backfill missing file_path/repo_path for relationships
        self.db.execute(
            f"MATCH ()-[r]->() WHERE r.file_path IS NULL SET r.file_path = '{file_path}'"
        )
        self.db.execute(
            f"MATCH ()-[r]->() WHERE r.repo_path IS NULL SET r.repo_path = '{repo_path}'"
        )
        return

    def force_repo_path_for_file(self: MemgraphManager, file_path: str, repo_path: str) -> None:
        """Force-set repo_path on nodes and relationships for a specific file.

        Useful when previous ingests stored subfolder paths instead of the vault root.
        """
        # Nodes for this file
        self.db.execute(
            f"MATCH (n) WHERE n.file_path = '{file_path}' SET n.repo_path = '{repo_path}'"
        )
        # Relationships for this file
        self.db.execute(
            f"MATCH ()-[r]->() WHERE r.file_path = '{file_path}' SET r.repo_path = '{repo_path}'"
        )
        return

    def fix_repo_path_for_repo(self: MemgraphManager, vault_root: str) -> None:
        """Ensure all nodes/relationships under vault_root have repo_path set to vault_root.

        This corrects historical data that may have used per-file parent directories as repo_path.
        """
        root = os.path.abspath(vault_root)
        # Nodes whose files are inside the vault
        self.db.execute(
            f"MATCH (n) WHERE n.file_path STARTS WITH '{root}/' OR n.file_path = '{root}' SET n.repo_path = '{root}'"
        )
        # Relationships whose files are inside the vault
        self.db.execute(
            f"MATCH ()-[r]->() WHERE r.file_path STARTS WITH '{root}/' OR r.file_path = '{root}' SET r.repo_path = '{root}'"
        )
        return


if __name__ == '__main__':
    arch = MemgraphManager()

    example_reponame = 'History'
    example_repopath = os.path.join(os.path.dirname(
        __file__), 'examples', example_reponame)

    example_fname = 'napoleon.txt'
    example_fpath = os.path.join(example_repopath, example_fname)

    arch.update_embeddings(example_fpath)
    print(arch.get_schema_for_repo(example_repopath))
