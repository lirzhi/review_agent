from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import request
from urllib.error import HTTPError, URLError

from agent.agent_backend.llm.base import EmbeddingModelBase, ParseModelBase, RerankModelBase


def _load_api_key(conf: Dict[str, Any]) -> str:
    p = Path(str(conf.get("api_key_path", "") or ""))
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    return ""


def _post_json(url: str, payload: Dict[str, Any], api_key: str, timeout: int) -> Dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="ignore")
    data = json.loads(raw)
    return data if isinstance(data, dict) else {}


class GLMOCRParseModel(ParseModelBase):
    """GLM OCR parse model via /layout_parsing endpoint."""

    def __init__(self, conf: Dict[str, Any]):
        self.model = str(conf.get("model", "glm-ocr"))
        self.base_url = str(conf.get("base_url", "")).rstrip("/")
        self.timeout = int(conf.get("timeout", 60))
        self.api_key = _load_api_key(conf)

    def parse_layout(self, file: str) -> Dict[str, Any]:
        if not self.api_key or not self.base_url or not file:
            return {}
        try:
            return _post_json(
                url=f"{self.base_url}/layout_parsing",
                payload={"model": self.model, "file": file},
                api_key=self.api_key,
                timeout=self.timeout,
            )
        except (HTTPError, URLError, TimeoutError, ValueError, TypeError, json.JSONDecodeError):
            return {}
        except Exception:
            return {}

    def parse(
        self,
        messages: Optional[List[Dict[str, str]]] = None,
        file: str = "",
        default: str = "",
    ) -> str:
        file_ref = (file or "").strip()
        if not file_ref and messages:
            user_text = "\n".join(str(m.get("content", "")) for m in messages if m.get("role") == "user")
            user_text = user_text.strip()
            if user_text.startswith("http://") or user_text.startswith("https://"):
                file_ref = user_text
        if not file_ref:
            return default

        data = self.parse_layout(file_ref)
        if not data:
            return default
        md = str(data.get("md_results", "") or "").strip()
        return md or default


class GLMEmbeddingModel(EmbeddingModelBase):
    """GLM embedding model via /embeddings endpoint."""

    def __init__(self, conf: Dict[str, Any]):
        self.model = str(conf.get("model", "embedding-3"))
        self.base_url = str(conf.get("base_url", "")).rstrip("/")
        self.timeout = int(conf.get("timeout", 30))
        self.api_key = _load_api_key(conf)
        self.default_dimensions = conf.get("dimensions", None)

    def embed(self, text: str, dimensions: Optional[int] = None) -> List[float]:
        if not self.api_key or not self.base_url:
            return []
        payload: Dict[str, Any] = {
            "model": self.model,
            "input": text,
        }
        dim = dimensions if dimensions is not None else self.default_dimensions
        if dim is not None:
            try:
                payload["dimensions"] = int(dim)
            except Exception:
                pass
        try:
            data = _post_json(
                url=f"{self.base_url}/embeddings",
                payload=payload,
                api_key=self.api_key,
                timeout=self.timeout,
            )
            arr = data.get("data") if isinstance(data, dict) else None
            if isinstance(arr, list) and arr:
                emb = arr[0].get("embedding", [])
                if isinstance(emb, list):
                    return [float(x) for x in emb]
        except (HTTPError, URLError, TimeoutError, ValueError, TypeError, json.JSONDecodeError):
            return []
        except Exception:
            return []
        return []


class GLMRerankModel(RerankModelBase):
    """GLM rerank model via /rerank endpoint."""

    def __init__(self, conf: Dict[str, Any]):
        self.model = str(conf.get("model", "rerank"))
        self.base_url = str(conf.get("base_url", "")).rstrip("/")
        self.timeout = int(conf.get("timeout", 30))
        self.api_key = _load_api_key(conf)

    def rerank(self, query: str, documents: List[str], top_n: Optional[int] = None) -> List[float]:
        if not documents:
            return []
        if not self.api_key or not self.base_url:
            return [0.0 for _ in documents]

        payload: Dict[str, Any] = {
            "model": self.model,
            "query": query,
            "documents": documents,
        }
        if top_n is not None:
            try:
                payload["top_n"] = int(top_n)
            except Exception:
                pass

        try:
            data = _post_json(
                url=f"{self.base_url}/rerank",
                payload=payload,
                api_key=self.api_key,
                timeout=self.timeout,
            )
        except (HTTPError, URLError, TimeoutError, ValueError, TypeError, json.JSONDecodeError):
            return [0.0 for _ in documents]
        except Exception:
            return [0.0 for _ in documents]

        scores = [0.0 for _ in documents]
        results = data.get("results") if isinstance(data, dict) else None
        if isinstance(results, list):
            for item in results:
                try:
                    idx = int(item.get("index"))
                    score = float(item.get("relevance_score", 0.0))
                except Exception:
                    continue
                if 0 <= idx < len(scores):
                    scores[idx] = score
        return scores
