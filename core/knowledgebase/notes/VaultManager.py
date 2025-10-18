from __future__ import annotations

import pathlib
import os
import json
import time

from core.knowledgebase import constants
from core.knowledgebase.Utils import Utils
from core.knowledgebase.TextAnalizer import TextAnalizer
from core.knowledgebase.MemgraphManager import MemgraphManager
from core.knowledgebase.notes.CollectionManager import CollectionManager


class VaultManager:
    def __init__(self: VaultManager, vault_path: str) -> None:
        # Normalize to absolute path to ensure stable collection names and repo_path values
        self.vault_path = os.path.abspath(vault_path)
        self.ta = TextAnalizer()
        self.mm = MemgraphManager()
        self.cm = CollectionManager(self.vault_path)
        # Use a per-repo state file so multiple repos don't collide and we can clear selectively
        collection = Utils.collection_name_from_repo_path(self.vault_path)
        self.state_file_path = os.path.join(
            os.environ.get("CHROMA_DATA_DIR", "."), f"vault_state_{collection}.json")

    def _load_state(self) -> dict:
        if not os.path.exists(self.state_file_path):
            return {}
        with open(self.state_file_path, 'r') as f:
            return json.load(f)

    def _save_state(self, state: dict) -> None:
        with open(self.state_file_path, 'w') as f:
            json.dump(state, f, indent=4)

    def _current_mtime(self, file_path: str) -> float:
        try:
            return os.path.getmtime(file_path)
        except Exception:
            return float(int(time.time()))

    def add_file(self, file_path: str, file_content: str | None = None) -> None:
        # Always use the vault root as the repo_path for graph storage and queries
        repo_path = self.vault_path
        # Important: keep LLM context tight to avoid oversized prompts.
        # Use only this file's existing graph data rather than the entire repo.
        data = self.mm.export_data_for_file_path(file_path)

        # Ensure we have the file content; keep full text for Chroma, but clamp for LLM
        file_content = file_content or pathlib.Path(file_path).read_text()
        data_str = str(data) if data else ""

        # Clamp data/text for LLM to respect model input limits
        max_ctx = int(os.environ.get("LLM_UPDATE_CONTEXT_MAX_CHARS", "20000"))
        max_text = int(os.environ.get("LLM_UPDATE_TEXT_MAX_CHARS", "8000"))
        data_ctx = data_str[:max_ctx]
        text_ctx = file_content[:max_text]

        if isinstance(data, list) and len(data) == 0:
            # New file: generate create queries using clamped text
            res_queries = self.ta.text_to_cypher_create(
                text_ctx, repo_path, file_path)
        else:
            # Existing graph + new text: generate update queries using clamped contexts
            res_queries = self.ta.data_and_text_to_cypher_update(
                data_ctx, text_ctx, repo_path, file_path)

        # Execute graph updates and vector store updates
        self.mm.run_update_query(res_queries)
        # Pass full file_content to avoid reading from container filesystem and to embed complete text
        self.cm.add_file(file_path, file_content)
        self.mm.update_embeddings(file_path)
        # Normalize graph invariants post-ingest for this file/repo
        try:
            self.mm.normalize_after_ingest(file_path, repo_path)
            # Force-correct repo_path on nodes/relationships for this file in case older data used a subfolder
            self.mm.force_repo_path_for_file(file_path, repo_path)
        except Exception:
            pass
        # Update state
        state = self._load_state()
        state[file_path] = self._current_mtime(file_path)
        self._save_state(state)

    def update_file(self, file_path: str, file_content: str | None = None) -> None:
        self.delete_file(file_path)
        self.add_file(file_path, file_content)

    def delete_file(self, file_path: str) -> None:
        self.mm.delete_graph_for_file(file_path)
        self.cm.delete_file(file_path)
        # Update state
        state = self._load_state()
        if file_path in state:
            del state[file_path]
            self._save_state(state)

    def rename_file(self, old_file_path: str, new_file_path: str) -> None:
        self.mm.rename_file(old_file_path, new_file_path)
        self.cm.rename_file(old_file_path, new_file_path)
        # Update state
        state = self._load_state()
        new_mtime = self._current_mtime(new_file_path)
        if old_file_path in state:
            del state[old_file_path]
        state[new_file_path] = new_mtime
        self._save_state(state)

    def populate_vault(self: VaultManager) -> dict:
        previous_state = self._load_state()
        current_files = Utils.get_all_files_recursive(self.vault_path)
        current_state = {}
        stats = {"new": 0, "modified": 0, "deleted": 0, "errors": []}

        # Identify new and modified files
        for file_path in current_files:
            try:
                mtime = os.path.getmtime(file_path)
                current_state[file_path] = mtime

                if file_path not in previous_state:
                    print(f"New file detected: {file_path}")
                    try:
                        self.add_file(file_path)
                        stats["new"] += 1
                    except Exception as e:
                        stats["errors"].append({"file": file_path, "error": str(e)})
                elif mtime > previous_state[file_path]:
                    print(f"Modified file detected: {file_path}")
                    try:
                        self.update_file(file_path)
                        stats["modified"] += 1
                    except Exception as e:
                        stats["errors"].append({"file": file_path, "error": str(e)})
            except Exception as e:
                stats["errors"].append({"file": file_path, "error": str(e)})

        # Identify deleted files
        deleted_files = set(previous_state.keys()) - set(current_state.keys())
        for file_path in deleted_files:
            print(f"Deleted file detected: {file_path}")
            try:
                self.delete_file(file_path)
                stats["deleted"] += 1
            except Exception as e:
                stats["errors"].append({"file": file_path, "error": str(e)})
        
        self._save_state(current_state)
        # As a final pass, ensure all nodes/relationships under this vault have the correct repo_path value
        try:
            self.mm.fix_repo_path_for_repo(self.vault_path)
        except Exception:
            pass
        return stats
