from agent.agent_backend.database.vector.milvus_db import MilvusDB


class VectorStore:
    def __init__(self, collection: str = "agent_collection"):
        self.db = MilvusDB(collection)

    def add(self, item_id: str, vector: list[float], text: str, metadata: dict | None = None) -> None:
        self.db.insert(item_id, vector, text, metadata=metadata)

    def search(self, vector: list[float], top_k: int = 5, filters: dict | None = None):
        return self.db.search(vector, top_k, filters=filters)

    def delete(self, item_id: str) -> None:
        self.db.delete(item_id)

    def delete_by_doc(self, doc_id: str) -> int:
        return self.db.delete_by_doc(doc_id)

    def count(self) -> int:
        return self.db.count()

    def list_by_doc(self, doc_id: str):
        return self.db.list_by_doc(doc_id)
