from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict

from agent.agent_backend.llm.base import ChatModelBase, EmbeddingModelBase, ParseModelBase, RerankModelBase
from agent.agent_backend.llm.model_setting import get_active_model_name, get_model_conf
from agent.agent_backend.llm.providers.glm_models import GLMEmbeddingModel, GLMOCRParseModel, GLMRerankModel
from agent.agent_backend.llm.providers.local_models import (
    HashEmbeddingModel,
    HashRerankModel,
    LexicalRerankModel,
    OpenAICompatibleEmbeddingModel,
)
from agent.agent_backend.llm.providers.openai_compatible import OpenAICompatibleTextModel


class _NullChatModel(ChatModelBase, ParseModelBase):
    def chat(self, messages, default: str = "") -> str:
        return default

    def parse(self, messages=None, file: str = "", default: str = "") -> str:
        return default


class _NullEmbeddingModel(EmbeddingModelBase):
    def embed(self, text: str, dimensions=None):
        return []


class _NullRerankModel(RerankModelBase):
    def rerank(self, query: str, documents, top_n=None):
        return [0.0 for _ in documents]


class ModelFactory:
    @staticmethod
    def _build_model(name: str, conf: Dict[str, Any]):
        kind = str(conf.get("kind", "")).strip().lower()
        if kind == "openai_chat":
            return OpenAICompatibleTextModel(conf)
        if kind == "openai_embedding":
            return OpenAICompatibleEmbeddingModel(conf)
        if kind == "glm_embedding":
            return GLMEmbeddingModel(conf)
        if kind == "hash_embedding":
            return HashEmbeddingModel(conf)
        if kind == "glm_ocr_parse":
            return GLMOCRParseModel(conf)
        if kind == "glm_rerank":
            return GLMRerankModel(conf)
        if kind == "lexical_rerank":
            return LexicalRerankModel()
        if kind == "hash_rerank":
            return HashRerankModel()
        return None

    @classmethod
    @lru_cache(maxsize=64)
    def by_name(cls, model_name: str):
        conf = get_model_conf(model_name)
        model = cls._build_model(model_name, conf)
        return model

    @classmethod
    def chat_model(cls) -> ChatModelBase:
        model = cls.by_name(get_active_model_name("chat"))
        return model if isinstance(model, ChatModelBase) else _NullChatModel()

    @classmethod
    def parse_model(cls) -> ParseModelBase:
        model = cls.by_name(get_active_model_name("parse"))
        return model if isinstance(model, ParseModelBase) else _NullChatModel()

    @classmethod
    def embedding_model(cls) -> EmbeddingModelBase:
        model = cls.by_name(get_active_model_name("embedding"))
        return model if isinstance(model, EmbeddingModelBase) else _NullEmbeddingModel()

    @classmethod
    def rerank_model(cls) -> RerankModelBase:
        model = cls.by_name(get_active_model_name("rerank"))
        return model if isinstance(model, RerankModelBase) else _NullRerankModel()
