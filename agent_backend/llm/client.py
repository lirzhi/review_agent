from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from agent.agent_backend.llm.factory import ModelFactory


class LLMClient:
    """
    Unified LLM facade.
    - chat: conversational generation model
    - parse: parsing/extraction model
    - embed: embedding model
    - rerank: rerank model
    """

    def __init__(self):
        self._chat_model = ModelFactory.chat_model()
        self._parse_model = ModelFactory.parse_model()
        self._embedding_model = ModelFactory.embedding_model()
        self._rerank_model = ModelFactory.rerank_model()
        self.chat_context_max_chars = int(os.getenv("LLM_CHAT_CONTEXT_MAX_CHARS", "200000"))
        self.embedding_context_max_chars = int(os.getenv("LLM_EMBED_CONTEXT_MAX_CHARS", "8000"))

    def _trim_messages_for_chat(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        if self.chat_context_max_chars <= 0:
            return messages
        out: List[Dict[str, str]] = []
        total = 0
        # Keep latest messages first within budget, then reverse back.
        for m in reversed(messages or []):
            role = str(m.get("role", "user"))
            content = str(m.get("content", ""))
            remain = self.chat_context_max_chars - total
            if remain <= 0:
                break
            piece = content[:remain]
            out.append({"role": role, "content": piece})
            total += len(piece)
        out.reverse()
        return out

    def _trim_text_for_embedding(self, text: str) -> str:
        if self.embedding_context_max_chars <= 0:
            return text or ""
        return (text or "")[: self.embedding_context_max_chars]

    def chat(self, messages: List[Dict[str, str]], default: str = "") -> str:
        trimmed = self._trim_messages_for_chat(messages)
        return self._chat_model.chat(messages=trimmed, default=default)

    def parse(
        self,
        messages: Optional[List[Dict[str, str]]] = None,
        file: str = "",
        default: str = "",
    ) -> str:
        trimmed = self._trim_messages_for_chat(messages or [])
        return self._parse_model.parse(messages=trimmed, file=file, default=default)

    def parse_layout(self, file: str) -> Dict[str, Any]:
        if hasattr(self._parse_model, "parse_layout"):
            try:
                data = self._parse_model.parse_layout(file)
                return data if isinstance(data, dict) else {}
            except Exception:
                return {}
        return {}

    def embed(self, text: str, dimensions: Optional[int] = None) -> List[float]:
        safe_text = self._trim_text_for_embedding(text)
        return self._embedding_model.embed(safe_text, dimensions=dimensions)

    def batch_embed(self, texts: List[str]) -> List[List[float]]:
        return self._embedding_model.batch_embed(texts)

    def rerank(self, query: str, documents: List[str], top_n: Optional[int] = None) -> List[float]:
        return self._rerank_model.rerank(query=query, documents=documents, top_n=top_n)

    @staticmethod
    def extract_json(raw_text: str) -> Optional[Any]:
        if not raw_text:
            return None
        text = raw_text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
        try:
            return json.loads(text)
        except Exception:
            pass
        m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
        if not m:
            return None
        try:
            return json.loads(m.group(1))
        except Exception:
            return None
