from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from agent.agent_backend.llm.client import LLMClient
from agent.agent_backend.prompts.template_manager import PromptTemplateManager


class PlannerReviewerAgent:
    """Unified runtime agent for chapter planning and review."""

    def __init__(self) -> None:
        self.llm = LLMClient()
        self.prompts = PromptTemplateManager("pre_review_agent_prompt")

    def describe(self) -> Dict[str, Any]:
        return {
            "name": "planner_reviewer",
            "modes": ["plan", "review"],
            "inputs": [
                "task_id",
                "section_id",
                "section_name",
                "registration_class",
                "review_domain",
                "product_type",
                "raw_text",
                "focus_points",
                "historical_experience",
                "retrieved_materials",
            ],
            "outputs": ["planner_result", "review_result"],
        }

    @staticmethod
    def _safe_list(value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        out: List[str] = []
        seen = set()
        for item in value:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            out.append(text)
        return out

    @staticmethod
    def _compact_text(text: str, max_len: int = 96) -> str:
        value = re.sub(r"\s+", " ", str(text or "").strip())
        if not value:
            return ""
        if len(value) <= max_len:
            return value
        for sep in ["；", ";", "。", ".", "，", ",", " "]:
            idx = value.find(sep)
            if 0 < idx <= max_len:
                value = value[:idx]
                break
        return value[:max_len].strip(" ,;，。")

    def _normalize_query_list(self, value: Any, max_len: int = 96) -> List[str]:
        out: List[str] = []
        seen = set()
        for item in self._safe_list(value):
            compact = self._compact_text(item, max_len=max_len)
            if not compact or compact in seen:
                continue
            seen.add(compact)
            out.append(compact)
        return out

    def _fallback_plan(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        section_id = str(payload.get("section_id", "") or "")
        section_name = str(payload.get("section_name", "") or "")
        registration_class = self._compact_text(str(payload.get("registration_class", "") or ""), max_len=48)
        review_domain = self._compact_text(str(payload.get("review_domain", "") or ""), max_len=32)
        product_type = self._compact_text(str(payload.get("product_type", "") or ""), max_len=32)
        focus_points = self._normalize_query_list(payload.get("focus_points", []), max_len=48)
        base_terms = [x for x in [section_name, product_type, review_domain, registration_class] if x]
        query_list: List[str] = []
        for point in focus_points[:4]:
            query = self._compact_text(" ".join(base_terms + [point]), max_len=96)
            if query:
                query_list.append(query)
        if not query_list:
            query_list = [self._compact_text(" ".join([x for x in [section_name, product_type, review_domain] if x]), max_len=96)]
        query_list = [item for item in query_list if item]
        if not query_list:
            query_list = [self._compact_text(section_id or section_name or "章节检索", max_len=96)]
        return {
            "section_id": section_id,
            "query_list": query_list,
            "retrieval_plan": [
                {"source_type": "指导原则", "purpose": "核对章节规范要求和研究重点", "query_subset": query_list[:2]},
                {"source_type": "ICH", "purpose": "核对国际技术要求", "query_subset": query_list[:1]},
                {"source_type": "法律法规", "purpose": "核对注册法规和申报要求", "query_subset": [self._compact_text(section_id or section_name, max_len=64)]},
                {"source_type": "药典数据", "purpose": "核对药典标准和检查项目", "query_subset": query_list[:1]},
                {"source_type": "历史经验", "purpose": "补充历史高风险问题和经验提醒", "query_subset": [self._compact_text(section_name or section_id, max_len=64)]},
            ],
            "priority_sources": ["指导原则", "ICH", "法律法规", "药典数据", "历史经验"],
            "expected_evidence_types": focus_points[:5],
            "missing_info_flags": [],
        }

    def plan(self, payload: Dict[str, Any], prompt_config: Dict[str, Any] | None = None) -> Dict[str, Any]:
        prompt = self.prompts.render("chapter_planner.j2", payload, prompt_config=prompt_config or {})
        default_data = self._fallback_plan(payload)
        raw = self.llm.chat(
            messages=[
                {"role": "system", "content": "你是药学预审规划智能体，只输出合法 JSON，不输出审评结论。"},
                {"role": "user", "content": prompt},
            ],
            default=json.dumps(default_data, ensure_ascii=False),
        )
        data = self.llm.extract_json(raw)
        if not isinstance(data, dict):
            data = default_data
        data.setdefault("section_id", str(payload.get("section_id", "") or ""))
        data["query_list"] = self._normalize_query_list(data.get("query_list", []), max_len=96)[:8]
        if not data["query_list"]:
            data["query_list"] = default_data["query_list"]
        retrieval_plan = data.get("retrieval_plan", [])
        if not isinstance(retrieval_plan, list):
            data["retrieval_plan"] = default_data["retrieval_plan"]
        else:
            normalized_plan = []
            for item in retrieval_plan:
                if not isinstance(item, dict):
                    continue
                normalized_plan.append(
                    {
                        "source_type": str(item.get("source_type", "") or "").strip(),
                        "purpose": self._compact_text(str(item.get("purpose", "") or ""), max_len=64),
                        "query_subset": self._normalize_query_list(item.get("query_subset", []), max_len=96)[:4] or data["query_list"][:2],
                    }
                )
            data["retrieval_plan"] = normalized_plan or default_data["retrieval_plan"]
        data["priority_sources"] = self._safe_list(data.get("priority_sources", [])) or default_data["priority_sources"]
        data["expected_evidence_types"] = self._safe_list(data.get("expected_evidence_types", []))
        data["missing_info_flags"] = self._safe_list(data.get("missing_info_flags", []))
        return data

    def _fallback_review(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        section_id = str(payload.get("section_id", "") or "")
        raw_text = str(payload.get("raw_text", "") or "").strip()
        focus_points = self._safe_list(payload.get("focus_points", []))
        retrieved_materials = payload.get("retrieved_materials", []) if isinstance(payload.get("retrieved_materials", []), list) else []
        evidence_refs: List[str] = []
        for item in retrieved_materials[:5]:
            if not isinstance(item, dict):
                continue
            source_type = str(item.get("source_type", "") or "").strip()
            title = str(item.get("title", "") or "").strip()
            if title:
                evidence_refs.append(f"{source_type}:{title}" if source_type else title)
        missing_points = focus_points[:5]
        conclusion = "unsupported"
        if raw_text:
            conclusion = "insufficient_information"
        if raw_text and evidence_refs:
            conclusion = "partially_supported"
        return {
            "section_id": section_id,
            "section_summary": raw_text[:240],
            "supported_points": [],
            "unsupported_points": [],
            "missing_points": missing_points,
            "risk_points": missing_points[:3],
            "pre_review_conclusion": conclusion,
            "questions": [
                {
                    "issue": f"章节仍缺少关键信息：{item}",
                    "basis": item,
                    "requested_action": f"请补充与“{item}”直接相关的原始研究内容、方法依据或法规支撑。",
                }
                for item in missing_points[:3]
            ],
            "evidence_refs": evidence_refs,
            "fact_basis": {
                "explicit_in_text": [],
                "supported_by_retrieval": evidence_refs,
                "based_on_experience_warning": [],
            },
            "confidence": "low",
        }

    def review(self, payload: Dict[str, Any], prompt_config: Dict[str, Any] | None = None) -> Dict[str, Any]:
        prompt = self.prompts.render("chapter_reviewer.j2", payload, prompt_config=prompt_config or {})
        default_data = self._fallback_review(payload)
        raw = self.llm.chat(
            messages=[
                {"role": "system", "content": "你是药学预审章节审评智能体，只输出合法 JSON，所有结论都必须受原文和证据约束。"},
                {"role": "user", "content": prompt},
            ],
            default=json.dumps(default_data, ensure_ascii=False),
        )
        data = self.llm.extract_json(raw)
        if not isinstance(data, dict):
            data = default_data
        data.setdefault("section_id", str(payload.get("section_id", "") or ""))
        for key in ["supported_points", "unsupported_points", "missing_points", "risk_points", "evidence_refs"]:
            data[key] = self._safe_list(data.get(key, []))
        questions = []
        if isinstance(data.get("questions", []), list):
            for item in data.get("questions", []):
                if not isinstance(item, dict):
                    continue
                issue = str(item.get("issue", "") or "").strip()
                basis = str(item.get("basis", "") or "").strip()
                requested_action = str(item.get("requested_action", "") or "").strip()
                if issue and basis and requested_action:
                    questions.append(
                        {
                            "issue": issue,
                            "basis": basis,
                            "requested_action": requested_action,
                        }
                    )
        data["questions"] = questions
        fact_basis = data.get("fact_basis", {})
        if not isinstance(fact_basis, dict):
            fact_basis = {}
        data["fact_basis"] = {
            "explicit_in_text": self._safe_list(fact_basis.get("explicit_in_text", [])),
            "supported_by_retrieval": self._safe_list(fact_basis.get("supported_by_retrieval", [])),
            "based_on_experience_warning": self._safe_list(fact_basis.get("based_on_experience_warning", [])),
        }
        confidence = str(data.get("confidence", "medium") or "medium").strip().lower()
        if confidence not in {"low", "medium", "high"}:
            confidence = "medium"
        data["confidence"] = confidence
        conclusion = str(data.get("pre_review_conclusion", "") or "").strip()
        if conclusion not in {"supported", "partially_supported", "unsupported", "insufficient_information"}:
            data["pre_review_conclusion"] = default_data["pre_review_conclusion"]
        return data
