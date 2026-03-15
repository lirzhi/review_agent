from typing import Any, Dict, List, Optional

from agent.agent_backend.database.vector.vector_manager import VectorManager


class MilvusDB:
    """
    Local in-memory replacement for vector DB operations.
    Keeps API simple and deterministic for backend RAG flow.
    """

    def __init__(self, collection_name: str = "agent_collection"):
        self.collection_name = collection_name
        self._manager = VectorManager()

    def insert(self, vec_id: str, vector: List[float], text: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        self._manager.upsert(vec_id, vector, text=text, metadata=metadata or {})

    def search(self, query_vector: List[float], top_k: int = 5, filters: Optional[Dict[str, Any]] = None):
        return self._manager.search(query_vector, top_k=top_k, filters=filters or {})

    def delete(self, vec_id: str) -> None:
        self._manager.delete(vec_id)

    def delete_by_doc(self, doc_id: str) -> int:
        return self._manager.delete_by_doc(doc_id)

    def count(self) -> int:
        return self._manager.count()

    def list_by_doc(self, doc_id: str):
        return self._manager.list_by_doc(doc_id)
