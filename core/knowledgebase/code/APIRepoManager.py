from __future__ import annotations

import requests
from typing import Optional, Dict, Any


class APIRepoManager:
    node_counter = 0

    def __init__(self: APIRepoManager, owner: str, repo: str, token: Optional[str] = None, ref: Optional[str] = None) -> None:
        self.owner = owner
        self.repo = repo
        self.token = token
        self.ref = ref

    @staticmethod
    def create_node(node_type: str, node_name: str, repo_path: str) -> tuple[str, str, str]:
        APIRepoManager.node_counter += 1
        unique_node_name = f"node{APIRepoManager.node_counter}"
        query = f"CREATE ({unique_node_name}:{node_type} {{name: '{node_name}'}})"
        set_query = f"SET {unique_node_name}.repo_path = '{repo_path}'"
        return query, set_query, unique_node_name

    @staticmethod
    def create_relationship(parent_node_name: str, child_node_name: str) -> str:
        query = f"MERGE ({parent_node_name})-[:CONTAINS]->({child_node_name})"
        return query

    @staticmethod
    def fetch_repository_contents(owner: str, repo: str, path: str = "", token: Optional[str] = None, ref: Optional[str] = None):
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        params: Dict[str, Any] = {}
        if ref:
            params["ref"] = ref
        headers: Dict[str, str] = {}
        if token:
            headers["Authorization"] = f"token {token}"
        response = requests.get(url, headers=headers or None, params=params or None)
        response_json = response.json()

        return response_json

    @staticmethod
    def cypher_from_contents(owner: str = "", repo: str = "", parent_node_name: str = "", path: str = "", token: Optional[str] = None, ref: Optional[str] = None):
        contents = APIRepoManager.fetch_repository_contents(owner, repo, path, token=token, ref=ref)
        create_queries = []
        set_queries = []
        merge_queries = []

        for item in contents:
            if 'type' in item and 'name' in item:
                if item['type'] == 'dir':
                    query, set_query, unique_node_name = APIRepoManager.create_node(
                        "Dir", item['name'], repo)
                    create_queries.append(query)
                    set_queries.append(set_query)
                    merge_queries.append(APIRepoManager.create_relationship(
                        parent_node_name, unique_node_name))

                    c_queries, s_queries, m_queries = APIRepoManager.cypher_from_contents(
                        owner, repo, unique_node_name, item['path'], token=token, ref=ref)
                    create_queries.extend(c_queries)
                    set_queries.extend(s_queries)
                    merge_queries.extend(m_queries)
                elif item['type'] == 'file':
                    query, set_query, unique_node_name = APIRepoManager.create_node(
                        "File", item['name'], repo)
                    create_queries.append(query)
                    set_queries.append(set_query)
                    merge_queries.append(APIRepoManager.create_relationship(
                        parent_node_name, unique_node_name))

        return create_queries, set_queries, merge_queries

    def generate_cypher(self):
        create_queries, set_queries, merge_queries = [], [], []

        # Use a stable repo_path identifier for all nodes
        repo_path = f"github://{self.owner}/{self.repo}"

        query, set_query, repo_node_name = APIRepoManager.create_node(
            "Repo", self.repo, repo_path)
        create_queries.append(query)
        set_queries.append(set_query)

        c_queries, s_queries, m_queries = APIRepoManager.cypher_from_contents(
            self.owner, repo_path, repo_node_name, token=self.token, ref=self.ref)

        create_queries.extend(c_queries)
        set_queries.extend(s_queries)
        merge_queries.extend(m_queries)

        return '\n'.join(create_queries + set_queries + merge_queries)


if __name__ == "__main__":
    owner = "pkukic"
    repo = "Quadris"
    arm = APIRepoManager(owner, repo)
    print(arm.generate_cypher())
