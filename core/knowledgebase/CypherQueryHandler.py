from typing import List
import json


class CypherQueryHandler:

    @staticmethod
    def get_check_if_db_empty_query() -> str:
        return (f"MATCH (n)"
                f"RETURN count(n) AS nodes")

    @staticmethod
    def get_export_for_repo_path_query(repo_path: str) -> str:
        return (f"MATCH p=(n {{ repo_path: '{repo_path}' }})-[r]->(m {{ repo_path: '{repo_path}' }}) "
                f"WITH project(p) AS repo_specific_subgraph "
                f"RETURN repo_specific_subgraph")

    @staticmethod
    def get_export_for_file_path_query(file_path: str) -> str:
        return (f"MATCH p=(n {{ file_path: '{file_path}' }})-[r]->(m {{ file_path: '{file_path}' }}) "
                f"WITH project(p) AS file_specific_subgraph "
                f"RETURN file_specific_subgraph")

    @staticmethod
    def get_isolated_nodes_for_repo_query(repo_path: str) -> str:
        # Nodes with no relationships in the given repo
        return (
            f"MATCH (n {{ repo_path: '{repo_path}' }}) "
            f"OPTIONAL MATCH (n)-[r]-() "
            f"WITH n, count(r) AS deg "
            f"WHERE deg = 0 "
            f"RETURN n AS node"
        )

    @staticmethod
    def get_isolated_nodes_for_file_query(file_path: str) -> str:
        # Nodes with no relationships in the given file
        return (
            f"MATCH (n {{ file_path: '{file_path}' }}) "
            f"OPTIONAL MATCH (n)-[r]-() "
            f"WITH n, count(r) AS deg "
            f"WHERE deg = 0 "
            f"RETURN n AS node"
        )

    @staticmethod
    def get_delete_all_query() -> str:
        return (f"MATCH (n) "
                "DETACH DELETE n")

    @staticmethod
    def get_delete_all_for_repo_query(repo_path: str) -> str:
        return (f"MATCH (n) "
                f"WHERE n.repo_path = '{repo_path}' "
                f"DETACH DELETE n")

    @staticmethod
    def get_delete_graph_for_file_query(file_path: str) -> str:
        return (f"MATCH (n) "
                f"WHERE n.file_path = '{file_path}' "
                f"DETACH DELETE n")

    @staticmethod
    def get_rename_file_query(old_file_path: str, new_file_path: str) -> str:
        return (
            f"MATCH (n) "
            f"WHERE n.file_path = '{old_file_path}' "
            f"SET n.file_path = '{new_file_path}'"
        )

    @staticmethod
    def get_rename_relationships_query(old_file_path: str, new_file_path: str) -> str:
        return (f"MATCH ()-[r]->() "
                f"WHERE r.file_path = '{old_file_path}' "
                f"SET r.file_path = '{new_file_path}'")

    @staticmethod
    def get_strings_to_embed_query(file_path: str) -> str:
        return (f"MATCH (n) "
                f"OPTIONAL MATCH (n)-[r]->(m) "
                f"WHERE n.file_path = '{file_path}' "
                f"RETURN ID(n) as Node_ID, "
                f"n.name as Node_Name, "
                f"labels(n)[0] as Node_Type, "
                f"collect({{Neighbour_Name: m.name, Neighbour_Type: labels(m)[0], Relationship_Type: type(r)}}) as Connections")

    @staticmethod
    def get_node_description_query(node_id: int) -> str:
        return (f"MATCH (n) "
                f"WHERE ID(n) = {node_id} "
                f"OPTIONAL MATCH (n)-[r1]->(m) "
                f"OPTIONAL MATCH (p)-[r2]->(n) "
                f"RETURN ID(n) as Node_ID,  "
                f"n.name as Node_Name, "
                f"labels(n)[0] as Node_Type, "
                "collect({ Neighbour_Name: m.name, Neighbour_Type: labels(m)[0], Relationship_Type: type(r1) }) as In_Connections, "
                "collect({ Neighbour_Name: p.name, Neighbour_Type: labels(p)[0], Relationship_Type: type(r2) }) as Out_Connections")

    @staticmethod
    def get_set_embeddings_query(node_id: str, embeddings: List[float]) -> str:
        emb_str = json.dumps(embeddings)
        return (f"MATCH (n) "
                f"WHERE ID(n) = {node_id} "
                f"SET n.embeddings = {emb_str} ")

    @staticmethod
    def get_tmp_create_query() -> str:
        # Parameterized; embeddings and req provided via execute parameters
        return ("CREATE (:Temp {req: $req, embeddings: $embeddings}) ")

    @staticmethod
    def get_tmp_delete_query() -> str:
        # Parameterized by req to delete only the temp node for this request
        return ("MATCH (n:Temp {req: $req}) "
                "DETACH DELETE n ")

    @staticmethod
    def get_schema_for_repo_query(repo_path: str) -> str:
        return (f"MATCH p=(n {{ repo_path: '{repo_path}' }})-[r]->(m {{ repo_path: '{repo_path}' }}) "
                f"WITH project(p) AS repo_specific_subgraph "
                f"CALL llm_util.schema(repo_specific_subgraph, 'prompt_ready') "
                f"YIELD schema "
                f"RETURN schema")

    @staticmethod
    def get_vector_search_query(limit: int = 3) -> str:
        lim = max(1, int(limit))
        return ("MATCH (tmp:Temp {req: $req}) "
                "WITH tmp LIMIT 1 "
                "MATCH (m) "
                "WHERE m.embeddings IS NOT NULL AND NOT m:Temp "
                "WITH m, tmp "
                "WITH m, m.embeddings AS a, tmp.embeddings AS b "
                "WITH m, a, b, CASE WHEN size(a) < size(b) THEN size(a) ELSE size(b) END AS dim "
                "WITH m, dim, "
                "reduce(s = 0.0, i IN range(0, dim-1) | s + (a[i] * b[i])) AS dot, "
                "reduce(s = 0.0, i IN range(0, dim-1) | s + (a[i] * a[i])) AS normA2, "
                "reduce(s = 0.0, i IN range(0, dim-1) | s + (b[i] * b[i])) AS normB2 "
                "WITH m, dot, sqrt(normA2) AS normA, sqrt(normB2) AS normB "
                "WITH m, CASE WHEN normA = 0 OR normB = 0 THEN 0.0 ELSE dot / (normA * normB) END AS cosine_similarity "
                "RETURN ID(m) AS `ID(node1)`, cosine_similarity "
                "ORDER BY cosine_similarity DESC "
                f"LIMIT {lim}")

    @staticmethod
    def get_embeddings_for_node_query(node_id: int) -> str:
        return (f"MATCH (m) "
                f"WHERE ID(m) = {node_id} "
                f"RETURN m.embeddings as embeddings")
