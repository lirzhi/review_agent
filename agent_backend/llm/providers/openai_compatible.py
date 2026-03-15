from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import OpenAI

from agent.agent_backend.llm.base import ChatModelBase, ParseModelBase


def _read_api_key(conf: Dict[str, Any]) -> str:
    p = Path(str(conf.get("api_key_path", "") or ""))
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    return ""


class OpenAICompatibleTextModel(ChatModelBase, ParseModelBase):
    def __init__(self, conf: Dict[str, Any]):
        self.model = str(conf.get("model", ""))
        self.base_url = str(conf.get("base_url", "")).strip()
        self.timeout = int(conf.get("timeout", 30))
        self.api_key = _read_api_key(conf)
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=self.timeout)

    def _run(self, messages: List[Dict[str, str]], default: str = "") -> str:
        if not self.model or not self.api_key or not self.base_url:
            return default
        try:
            resp = self.client.chat.completions.create(model=self.model, messages=messages)
            content = resp.choices[0].message.content if resp and resp.choices else ""
            return str(content or "").strip() or default
        except Exception:
            return default

    def chat(self, messages: List[Dict[str, str]], default: str = "") -> str:
        return self._run(messages=messages, default=default)

    def parse(
        self,
        messages: Optional[List[Dict[str, str]]] = None,
        file: str = "",
        default: str = "",
    ) -> str:
        if not messages:
            return default
        return self._run(messages=messages, default=default)
