import os
from core.knowledgebase.MemgraphManager import MemgraphManager
from core.knowledgebase.notes.CollectionManager import CollectionManager
from core.knowledgebase.notes.VaultManager import VaultManager


class Initializer:
    @staticmethod
    def init_vault_data() -> None:
        mm = MemgraphManager()
        cm = CollectionManager()

        mm.delete_all()
        cm.delete_all()

        vault_path = os.environ.get("OBSIDIAN_VAULT_PATH")
        if not vault_path:
            raise ValueError(
                "OBSIDIAN_VAULT_PATH environment variable not set.")

        if not os.path.isdir(vault_path):
            raise FileNotFoundError(
                f"The specified vault path does not exist or is not a directory: {vault_path}")

        vault_manager = VaultManager(vault_path)
        vault_manager.populate_vault()

        return


if __name__ == '__main__':
    Initializer.init_vault_data()
