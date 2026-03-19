from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List

from agent.agent_backend.llm.client import LLMClient
from agent.agent_backend.prompts.template_manager import PromptTemplateManager


class FeedbackAgent:
    """Unified runtime agent for feedback analysis and patch proposal."""

    def __init__(self) -> None:
        self.llm = LLMClient()
        self.prompts = PromptTemplateManager("pre_review_agent_prompt")

    @staticmethod
    def _safe_list(value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        seen = set()
        out: List[str] = []
        for item in value:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            out.append(text)
        return out

    @staticmethod
    def _build_suffix_from_patches(patches: List[Dict[str, Any]], target_agent: str) -> str:
        relevant = [item for item in patches if isinstance(item, dict) and str(item.get("target_agent", "") or "").strip() == target_agent]
        if not relevant:
            return ""
        lines = ["动态补丁规则:"]
        for index, patch in enumerate(relevant, start=1):
            trigger = str(patch.get("trigger_condition", "") or "").strip()
            content = str(patch.get("patch_content", "") or "").strip()
            if not content:
                continue
            line = f"{index}. {content}"
            if trigger:
                line += f" 触发条件: {trigger}"
            lines.append(line)
        return "\n".join(lines).strip()

    def _fallback_analysis(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        decision = str(payload.get("decision", "") or "").lower()
        labels = {str(x).strip().lower() for x in payload.get("labels", []) or []}
        reference_inputs = payload.get("reference_inputs", {}) if isinstance(payload.get("reference_inputs", {}), dict) else {}
        retrieved_materials = reference_inputs.get("retrieved_materials", []) if isinstance(reference_inputs.get("retrieved_materials", []), list) else []
        polarity = "positive"
        error_types: List[str] = []
        if decision in {"false_positive", "rejected"}:
            polarity = "negative"
            error_types = ["over_inference"]
        elif decision in {"missed", "missing_risk"}:
            polarity = "negative"
            error_types = ["under_identification"]
            if not retrieved_materials:
                error_types = ["query_miss"]
        elif decision:
            polarity = "partial"
            error_types = ["focus_point_miss"]
        if "retrieval_miss" in labels:
            error_types = ["query_miss"]
        elif "wrong_reference" in labels:
            error_types = ["missing_regulatory_basis"]
        elif "style_issue" in labels:
            error_types = ["wording_not_actionable"]
        elif "reasoning_error" in labels:
            error_types = ["evidence_interpretation_error"]
        return {
            "section_id": str(payload.get("section_id", "") or ""),
            "feedback_polarity": polarity,
            "error_types": error_types,
            "primary_error_type": error_types[0] if error_types else "",
            "root_cause": str(payload.get("feedback_text", "") or "需要根据专家反馈修正章节预审策略。"),
            "attention_points_next_time": self._safe_list(payload.get("focus_points", []))[:5],
            "retrieval_missed": [],
            "new_experience": [],
            "uncertainty_note": "",
        }

    def analyze_feedback(self, payload: Dict[str, Any], prompt_config: Dict[str, Any] | None = None) -> Dict[str, Any]:
        prompt = self.prompts.render("feedback_analyzer.j2", payload, prompt_config=prompt_config or {})
        default_data = self._fallback_analysis(payload)
        raw = self.llm.chat(
            messages=[
                {"role": "system", "content": "你是反馈归因智能体，只输出合法 JSON，不能输出额外解释。"},
                {"role": "user", "content": prompt},
            ],
            default=json.dumps(default_data, ensure_ascii=False),
        )
        data = self.llm.extract_json(raw)
        if not isinstance(data, dict):
            data = default_data
        data["section_id"] = str(data.get("section_id", payload.get("section_id", "")) or "")
        polarity = str(data.get("feedback_polarity", default_data["feedback_polarity"]) or "").strip()
        if polarity not in {"positive", "negative", "partial"}:
            polarity = default_data["feedback_polarity"]
        data["feedback_polarity"] = polarity
        data["error_types"] = self._safe_list(data.get("error_types", []))
        data["primary_error_type"] = str(data.get("primary_error_type", data["error_types"][0] if data["error_types"] else "") or "")
        data["attention_points_next_time"] = self._safe_list(data.get("attention_points_next_time", []))
        data["retrieval_missed"] = self._safe_list(data.get("retrieval_missed", []))
        experiences = []
        if isinstance(data.get("new_experience", []), list):
            for item in data.get("new_experience", []):
                if not isinstance(item, dict):
                    continue
                exp_type = str(item.get("experience_type", "") or "").strip()
                content = str(item.get("content", "") or "").strip()
                scope = str(item.get("applicable_scope", "") or "").strip()
                if exp_type and content:
                    experiences.append(
                        {
                            "experience_type": exp_type,
                            "content": content,
                            "applicable_scope": scope or data["section_id"],
                        }
                    )
        data["new_experience"] = experiences
        if not data["new_experience"] and data["feedback_polarity"] in {"partial", "negative"}:
            exp_type_map = {
                "query_miss": "query_rule",
                "retrieval_scope_error": "query_rule",
                "retrieval_ranking_error": "query_rule",
                "historical_experience_missing": "query_rule",
                "section_fact_extraction_error": "review_rule",
                "focus_point_miss": "review_rule",
                "evidence_interpretation_error": "review_rule",
                "over_inference": "review_rule",
                "under_identification": "risk_pattern",
                "wrong_severity": "risk_pattern",
                "wording_not_actionable": "wording_rule",
                "missing_regulatory_basis": "wording_rule",
                "unhelpful_question_to_applicant": "wording_rule",
            }
            primary_error = str(data.get("primary_error_type", "") or "").strip()
            data["new_experience"] = [
                {
                    "experience_type": exp_type_map.get(primary_error, "review_rule"),
                    "content": str(data.get("root_cause", "") or payload.get("user_feedback_text", "") or "需要补充可复用的章节审评规则。"),
                    "applicable_scope": str(payload.get("section_id", "") or ""),
                }
            ]
        data["uncertainty_note"] = str(data.get("uncertainty_note", "") or "").strip()
        data["root_cause"] = str(data.get("root_cause", default_data["root_cause"]) or "").strip()
        return data

    def _fallback_patch(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        section_id = str(payload.get("section_id", "") or "")
        analysis = payload.get("feedback_analysis_result", {}) if isinstance(payload.get("feedback_analysis_result", {}), dict) else {}
        error_types = self._safe_list(analysis.get("error_types", []))
        patch_type = "reasoning_patch"
        if any(x in {"query_miss", "retrieval_scope_error", "retrieval_ranking_error", "historical_experience_missing"} for x in error_types):
            patch_type = "query_patch"
        if any(x in {"wording_not_actionable", "missing_regulatory_basis", "unhelpful_question_to_applicant"} for x in error_types):
            patch_type = "wording_patch"
        target_agent = "planner" if patch_type == "query_patch" else "pre_review"
        patch_content = str(analysis.get("root_cause", "") or payload.get("user_feedback_text", "") or "需要增加一条最小规则补丁。").strip()
        patches = [
            {
                "patch_id": f"patch_{uuid.uuid4().hex[:12]}",
                "patch_type": patch_type,
                "target_agent": target_agent,
                "target_scope": section_id,
                "trigger_condition": f"section_id == '{section_id}'",
                "patch_content": patch_content,
                "status": "candidate",
            }
        ]
        planner_suffix = self._build_suffix_from_patches(patches, "planner")
        review_suffix = self._build_suffix_from_patches(patches, "pre_review")
        return {
            "section_id": section_id,
            "patches": patches,
            "candidate_templates": {
                "planner_prompt_candidate": f"{str(payload.get('current_templates', {}).get('planner_prompt', '') or '').strip()}\n\n[DynamicPromptPatch]\n{planner_suffix}".strip() if planner_suffix else str(payload.get("current_templates", {}).get("planner_prompt", "") or ""),
                "pre_review_prompt_candidate": f"{str(payload.get('current_templates', {}).get('pre_review_prompt', '') or '').strip()}\n\n[DynamicPromptPatch]\n{review_suffix}".strip() if review_suffix else str(payload.get("current_templates", {}).get("pre_review_prompt", "") or ""),
                "feedback_analyzer_prompt_candidate": str(payload.get("current_templates", {}).get("feedback_analyzer_prompt", "") or ""),
                "feedback_optimizer_prompt_candidate": str(payload.get("current_templates", {}).get("feedback_optimizer_prompt", "") or ""),
            },
            "applicable_conditions": [section_id],
        }

    def propose_patch(self, payload: Dict[str, Any], prompt_config: Dict[str, Any] | None = None) -> Dict[str, Any]:
        prompt = self.prompts.render("feedback_optimizer.j2", payload, prompt_config=prompt_config or {})
        default_data = self._fallback_patch(payload)
        raw = self.llm.chat(
            messages=[
                {"role": "system", "content": "你是反馈优化智能体，只输出合法 JSON，只给最小 patch。"},
                {"role": "user", "content": prompt},
            ],
            default=json.dumps(default_data, ensure_ascii=False),
        )
        data = self.llm.extract_json(raw)
        if not isinstance(data, dict):
            data = default_data
        patches = []
        if isinstance(data.get("patches", []), list):
            for item in data.get("patches", []):
                if not isinstance(item, dict):
                    continue
                patch_type = str(item.get("patch_type", "") or "").strip()
                target_agent = str(item.get("target_agent", "") or "").strip()
                patch_content = str(item.get("patch_content", "") or "").strip()
                if not patch_type or not target_agent or not patch_content:
                    continue
                patches.append(
                    {
                        "patch_id": str(item.get("patch_id", "") or f"patch_{uuid.uuid4().hex[:12]}"),
                        "patch_type": patch_type,
                        "target_agent": target_agent,
                        "target_scope": str(item.get("target_scope", data.get("section_id", "")) or data.get("section_id", "")),
                        "trigger_condition": str(item.get("trigger_condition", "") or ""),
                        "patch_content": patch_content,
                        "status": str(item.get("status", "candidate") or "candidate"),
                    }
                )
        if not patches:
            patches = default_data["patches"]
        data["patches"] = patches
        planner_suffix = self._build_suffix_from_patches(patches, "planner")
        review_suffix = self._build_suffix_from_patches(patches, "pre_review")
        candidates = data.get("candidate_templates", {})
        if not isinstance(candidates, dict):
            candidates = default_data["candidate_templates"]
        planner_base = str(candidates.get("planner_prompt_candidate", "") or "").strip() or str(payload.get("current_templates", {}).get("planner_prompt", "") or "").strip()
        review_base = str(candidates.get("pre_review_prompt_candidate", "") or "").strip() or str(payload.get("current_templates", {}).get("pre_review_prompt", "") or "").strip()
        data["candidate_templates"] = {
            "planner_prompt_candidate": planner_base if "[DynamicPromptPatch]" in planner_base or not planner_suffix else f"{planner_base}\n\n[DynamicPromptPatch]\n{planner_suffix}".strip(),
            "pre_review_prompt_candidate": review_base if "[DynamicPromptPatch]" in review_base or not review_suffix else f"{review_base}\n\n[DynamicPromptPatch]\n{review_suffix}".strip(),
            "feedback_analyzer_prompt_candidate": str(candidates.get("feedback_analyzer_prompt_candidate", "") or payload.get("current_templates", {}).get("feedback_analyzer_prompt", "") or "").strip(),
            "feedback_optimizer_prompt_candidate": str(candidates.get("feedback_optimizer_prompt_candidate", "") or payload.get("current_templates", {}).get("feedback_optimizer_prompt", "") or "").strip(),
        }
        data["applicable_conditions"] = self._safe_list(data.get("applicable_conditions", [])) or default_data["applicable_conditions"]
        data["section_id"] = str(data.get("section_id", payload.get("section_id", "")) or "")
        return data
