from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from agent.agent_backend.database.vector.vector_db import Embedding
from agent.agent_backend.llm.factory import ModelFactory

_DEBUG_ONCE_KEYS: set[str] = set()
_VERBOSE = os.getenv("LLM_VERBOSE_LOG", "0").strip().lower() in {"1", "true", "yes", "on"}


def _debug_once(key: str, message: str) -> None:
    if key in _DEBUG_ONCE_KEYS:
        return
    _DEBUG_ONCE_KEYS.add(key)
    print(message)


def _debug(message: str) -> None:
    if _VERBOSE:
        print(message)


class LLMClient:
    """
    Unified LLM facade.
    - chat: conversational generation model
    - parse: temporarily routed to chat model only
    - embed: local Embedding from database/vector/vector_db.py
    - rerank: disabled for now
    """

    def __init__(self):
        self._chat_model = ModelFactory.chat_model()
        self._embedding_model = None
        self.chat_context_max_chars = int(os.getenv("LLM_CHAT_CONTEXT_MAX_CHARS", "200000"))
        self.embedding_context_max_chars = int(os.getenv("LLM_EMBED_CONTEXT_MAX_CHARS", "8000"))
        msg = (
            "[LLMDebug] LLMClient.__init__: "
            f"chat_model={type(self._chat_model).__name__}, "
            "parse_model=disabled(chat-only), "
            "embedding_model=lazy(Embedding), "
            "rerank_model=disabled, "
            f"chat_context_max_chars={self.chat_context_max_chars}, "
            f"embedding_context_max_chars={self.embedding_context_max_chars}"
        )
        _debug_once(f"llm_init:{msg}", msg)

    @staticmethod
    def _dump_messages(messages: List[Dict[str, str]]) -> str:
        try:
            return json.dumps(messages, ensure_ascii=False, indent=2)
        except Exception:
            return str(messages)

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

    def _get_embedding_model(self) -> Embedding:
        if self._embedding_model is None:
            self._embedding_model = Embedding()
        return self._embedding_model

    def chat(self, messages: List[Dict[str, str]], default: str = "") -> str:
        trimmed = self._trim_messages_for_chat(messages)
        _debug("[LLMDebug] chat.input.messages:")
        _debug(self._dump_messages(trimmed))
        _debug(f"[LLMDebug] chat.input.default: {default!r}")
        result = self._chat_model.chat(messages=trimmed, default=default)
        _debug("[LLMDebug] chat.output:")
        _debug(result)
        return result

    def parse(
        self,
        messages: Optional[List[Dict[str, str]]] = None,
        file: str = "",
        default: str = "",
    ) -> str:
        trimmed = self._trim_messages_for_chat(messages or [])
        _debug("[LLMDebug] parse.input.messages:")
        _debug(self._dump_messages(trimmed))
        _debug(f"[LLMDebug] parse.input.file: {file}")
        _debug(f"[LLMDebug] parse.input.default: {default!r}")
        if file:
            _debug("[LLMDebug] parse.note: dedicated parse model disabled, file parsing skipped")
            return default
        result = self._chat_model.chat(messages=trimmed, default=default)
        _debug("[LLMDebug] parse.output:")
        _debug(result)
        return result

    def parse_layout(self, file: str) -> Dict[str, Any]:
        _debug(f"[LLMDebug] parse_layout.input.file: {file}")
        _debug("[LLMDebug] parse_layout.note: disabled")
        return {}

    def embed(self, text: str, dimensions: Optional[int] = None) -> List[float]:
        safe_text = self._trim_text_for_embedding(text)
        _debug(f"[LLMDebug] embed.input.dimensions: {dimensions}")
        _debug("[LLMDebug] embed.input.text:")
        _debug(safe_text)
        _ = dimensions
        result = self._get_embedding_model().embed_query(safe_text)
        _debug(f"[LLMDebug] embed.output.vector_dim: {len(result)}")
        return result

    def batch_embed(self, texts: List[str]) -> List[List[float]]:
        _debug(f"[LLMDebug] batch_embed.input.count: {len(texts or [])}")
        _debug("[LLMDebug] batch_embed.input.texts:")
        _debug(json.dumps(texts or [], ensure_ascii=False, indent=2))
        result = self._get_embedding_model().convert_text_to_embedding(texts or [])
        _debug(f"[LLMDebug] batch_embed.output.count: {len(result or [])}")
        return result

    def rerank(self, query: str, documents: List[str], top_n: Optional[int] = None) -> List[float]:
        _debug(f"[LLMDebug] rerank.input.query: {query}")
        _debug(f"[LLMDebug] rerank.input.top_n: {top_n}")
        _debug("[LLMDebug] rerank.input.documents:")
        _debug(json.dumps(documents or [], ensure_ascii=False, indent=2))
        result = [0.0 for _ in (documents or [])]
        _debug("[LLMDebug] rerank.output.scores:")
        _debug(json.dumps(result or [], ensure_ascii=False))
        return result

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
