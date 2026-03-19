from __future__ import annotations

from typing import Any, Dict, List

from agent.agent_backend.llm.client import LLMClient
from agent.agent_backend.prompts.template_manager import PromptTemplateManager


class LeadReviewerAgent:
    """Aggregate reviewed sections into final run-level summary."""

    def __init__(self) -> None:
        self.llm = LLMClient()
        self.prompts = PromptTemplateManager("pre_review_agent_prompt")

    def describe(self) -> Dict[str, Any]:
        return {
            "name": "lead_reviewer",
            "description": "Aggregate section conclusions into overall conclusions and key supplement questions.",
            "inputs": ["section_results", "consistency_result", "qa_result"],
            "outputs": ["overall_conclusion", "risk_map", "key_questions"],
        }

    def summarize(
        self,
        project_meta: Dict[str, Any],
        section_results: List[Dict[str, Any]],
        consistency_result: Dict[str, Any],
        qa_result: Dict[str, Any],
        prompt_config: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        concise_sections = []
        for item in section_results[:40]:
            if not isinstance(item, dict):
                continue
            concise_sections.append({
                "section_id": item.get("section_id", ""),
                "section_name": item.get("section_name", ""),
                "risk_level": item.get("risk_level", "low"),
                "conclusion": item.get("conclusion", ""),
                "issues": item.get("highlighted_issues", []),
            })
        prompt = self.prompts.render(
            "lead_reviewer.j2",
            {
                "project_meta": project_meta,
                "section_results": concise_sections,
                "consistency_result": consistency_result,
                "qa_result": qa_result,
            },
            prompt_config=prompt_config or {},
        )
        raw = self.llm.chat(
            messages=[
                {"role": "system", "content": "你是总评汇总代理。只输出合法 JSON。"},
                {"role": "user", "content": prompt},
            ],
            default='{"overall_conclusion": "", "risk_map": [], "key_questions": [], "summary": ""}',
        )
        data = self.llm.extract_json(raw)
        if not isinstance(data, dict):
            return {"overall_conclusion": "", "risk_map": [], "key_questions": [], "summary": ""}
        return {
            "overall_conclusion": str(data.get("overall_conclusion", "") or "").strip(),
            "risk_map": [item for item in data.get("risk_map", []) if isinstance(item, dict)] if isinstance(data.get("risk_map", []), list) else [],
            "key_questions": [str(x).strip() for x in data.get("key_questions", []) if str(x).strip()] if isinstance(data.get("key_questions", []), list) else [],
            "summary": str(data.get("summary", "") or "").strip(),
        }
