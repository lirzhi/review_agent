from typing import List

from agent.agent_backend.llm.client import LLMClient


class EmbeddingService:
    """Unified embedding service routed by llm model settings."""

    def __init__(self):
        self.client = LLMClient()

    def embed(self, text: str) -> List[float]:
        vec = self.client.embed(text)
        if vec:
            return vec
        # Final fallback keeps old behavior predictable.
        vec = [0.0] * 128
        for i, ch in enumerate((text or "")[:2048]):
            vec[(ord(ch) + i) % 128] += 1.0
        return vec

    def batch_embed(self, texts: list[str]) -> list[list[float]]:
        out = self.client.batch_embed(texts)
        if out and all(isinstance(x, list) and len(x) > 0 for x in out):
            return out
        return [self.embed(t) for t in texts]
