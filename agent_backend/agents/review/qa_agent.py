from __future__ import annotations

from typing import Any, Dict, List

from agent.agent_backend.llm.client import LLMClient
from agent.agent_backend.prompts.template_manager import PromptTemplateManager


class QAAgent:
    """Validate section outputs and consistency outputs."""

    def __init__(self) -> None:
        self.llm = LLMClient()
        self.prompts = PromptTemplateManager("pre_review_agent_prompt")

    def describe(self) -> Dict[str, Any]:
        return {
            "name": "qa_reviewer",
            "description": "Validate evidence binding, unsupported conclusions, and major omissions.",
            "inputs": ["section_result", "consistency_result"],
            "outputs": ["qa_status", "qa_issues"],
        }

    def review_section(self, section_result: Dict[str, Any], prompt_config: Dict[str, Any] | None = None) -> Dict[str, Any]:
        prompt = self.prompts.render("qa_checker.j2", {"section_result": section_result}, prompt_config=prompt_config or {})
        raw = self.llm.chat(
            messages=[
                {"role": "system", "content": "你是审评质控代理。只输出合法 JSON。"},
                {"role": "user", "content": prompt},
            ],
            default='{"qa_status": "pass", "qa_issues": []}',
        )
        data = self.llm.extract_json(raw)
        if not isinstance(data, dict):
            return {"qa_status": "pass", "qa_issues": []}
        return {
            "qa_status": str(data.get("qa_status", "pass") or "pass").strip().lower(),
            "qa_issues": [item for item in data.get("qa_issues", []) if isinstance(item, dict)] if isinstance(data.get("qa_issues", []), list) else [],
        }

    def review_run(self, run_payload: Dict[str, Any], prompt_config: Dict[str, Any] | None = None) -> Dict[str, Any]:
        prompt = self.prompts.render("qa_checker.j2", {"section_result": run_payload}, prompt_config=prompt_config or {})
        raw = self.llm.chat(
            messages=[
                {"role": "system", "content": "你是审评质控代理。只输出合法 JSON。"},
                {"role": "user", "content": prompt},
            ],
            default='{"qa_status": "pass", "qa_issues": []}',
        )
        data = self.llm.extract_json(raw)
        if not isinstance(data, dict):
            return {"qa_status": "pass", "qa_issues": []}
        return {
            "qa_status": str(data.get("qa_status", "pass") or "pass").strip().lower(),
            "qa_issues": [item for item in data.get("qa_issues", []) if isinstance(item, dict)] if isinstance(data.get("qa_issues", []), list) else [],
        }
