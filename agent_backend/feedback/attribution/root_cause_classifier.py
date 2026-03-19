from __future__ import annotations

from typing import Dict, List


class RootCauseClassifier:
    """Classify feedback into coarse root-cause buckets."""

    RETRIEVAL_SUBCATEGORIES = {
        "query_miss",
        "retrieval_scope_error",
        "retrieval_ranking_error",
        "historical_experience_missing",
    }
    AGENT_SUBCATEGORIES = {
        "section_fact_extraction_error",
        "focus_point_miss",
        "evidence_interpretation_error",
        "over_inference",
        "under_identification",
        "wrong_severity",
    }
    PROMPT_SUBCATEGORIES = {
        "wording_not_actionable",
        "unhelpful_question_to_applicant",
    }
    RULE_SUBCATEGORIES = {
        "missing_regulatory_basis",
    }

    def classify(self, feedback_record: Dict[str, object], run_trace: Dict[str, object]) -> Dict[str, object]:
        trace_meta = self._extract_trace_meta(run_trace)
        sub_category = self._infer_sub_category(feedback_record, trace_meta)
        root_category = (
            self.classify_rag_issue(feedback_record, trace_meta, sub_category)
            or self.classify_agent_issue(feedback_record, trace_meta, sub_category)
            or self.classify_prompt_issue(feedback_record, trace_meta, sub_category)
            or self.classify_rule_issue(feedback_record, trace_meta, sub_category)
            or "general_issue"
        )
        confidence = self._infer_confidence(feedback_record, trace_meta, sub_category)
        evidence = {
            "feedback_labels": list(feedback_record.get("labels", []) or []),
            "issue_feedback_count": len(feedback_record.get("issue_feedback", []) or []),
            "paragraph_feedback_count": len(feedback_record.get("paragraph_feedback", []) or []),
            "evidence_feedback_count": len(feedback_record.get("evidence_feedback", []) or []),
            "retrieval_hit_count": trace_meta["retrieval_hit_count"],
            "effective_queries": trace_meta["effective_queries"],
            "source_breakdown": trace_meta["source_breakdown"],
            "error_breakdown": trace_meta["error_breakdown"],
            "retrieved_material_titles": trace_meta["retrieved_material_titles"],
            "agent_findings_count": trace_meta["findings_count"],
        }
        return {
            "category": root_category,
            "root_category": root_category,
            "sub_category": sub_category,
            "confidence": confidence,
            "evidence": evidence,
            "metadata": {
                "focus_point_count": trace_meta["focus_point_count"],
                "question_count": trace_meta["question_count"],
            },
        }

    def _extract_trace_meta(self, run_trace: Dict[str, object]) -> Dict[str, object]:
        coordination = run_trace.get("coordination", {}) if isinstance(run_trace.get("coordination"), dict) else {}
        retrieval = coordination.get("retrieval", {}) if isinstance(coordination.get("retrieval"), dict) else {}
        retrieval_detail = run_trace.get("retrieval_detail", {}) if isinstance(run_trace.get("retrieval_detail"), dict) else {}
        agent_meta = run_trace.get("agent", {}) if isinstance(run_trace.get("agent"), dict) else {}
        trace_payload = run_trace.get("trace", {}) if isinstance(run_trace.get("trace"), dict) else {}
        retrieved_materials = retrieval.get("retrieved_materials", []) if isinstance(retrieval.get("retrieved_materials", []), list) else []
        titles: List[str] = []
        for item in retrieved_materials:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "") or item.get("doc_title", "") or "").strip()
            if title:
                titles.append(title)
        return {
            "retrieval_hit_count": int(retrieval.get("hit_count", 0) or 0),
            "effective_queries": [str(x).strip() for x in retrieval.get("effective_queries", []) or [] if str(x).strip()],
            "source_breakdown": retrieval_detail.get("source_breakdown", {}) if isinstance(retrieval_detail.get("source_breakdown", {}), dict) else {},
            "error_breakdown": retrieval_detail.get("error_breakdown", {}) if isinstance(retrieval_detail.get("error_breakdown", {}), dict) else {},
            "retrieved_material_titles": titles,
            "findings_count": int(agent_meta.get("findings_count", 0) or 0),
            "focus_point_count": len(retrieval.get("focus_points", []) or []),
            "question_count": len(trace_payload.get("questions", []) or []) if isinstance(trace_payload.get("questions", []), list) else 0,
        }

    def _infer_sub_category(self, feedback_record: Dict[str, object], trace_meta: Dict[str, object]) -> str:
        labels = {str(x).lower() for x in feedback_record.get("labels", []) or []}
        feedback_text = str(feedback_record.get("feedback_text", "") or "").lower()
        decision = str(feedback_record.get("decision", "") or "").lower()
        error_breakdown = {str(k): int(v or 0) for k, v in (trace_meta.get("error_breakdown", {}) or {}).items()}
        source_breakdown = {str(k): int(v or 0) for k, v in (trace_meta.get("source_breakdown", {}) or {}).items()}
        retrieval_hit_count = int(trace_meta.get("retrieval_hit_count", 0) or 0)
        effective_queries = trace_meta.get("effective_queries", []) or []
        findings_count = int(trace_meta.get("findings_count", 0) or 0)

        if "retrieval_miss" in labels:
            return "query_miss"
        if "chunking_issue" in labels:
            return "retrieval_scope_error"
        if "wrong_reference" in labels:
            return "missing_regulatory_basis"
        if "reasoning_error" in labels:
            return "evidence_interpretation_error"
        if "style_issue" in labels:
            return "wording_not_actionable"

        ordered_breakdowns = [
            "query_miss",
            "retrieval_scope_error",
            "retrieval_ranking_error",
            "historical_experience_missing",
            "focus_point_miss",
            "evidence_interpretation_error",
            "over_inference",
            "under_identification",
            "wrong_severity",
            "missing_regulatory_basis",
            "wording_not_actionable",
            "unhelpful_question_to_applicant",
        ]
        for key in ordered_breakdowns:
            if error_breakdown.get(key, 0) > 0:
                return key

        if decision in {"missed", "missing_risk"}:
            if retrieval_hit_count <= 0 or not effective_queries:
                return "query_miss"
            if source_breakdown.get("历史经验", 0) <= 0 and "经验" in feedback_text:
                return "historical_experience_missing"
            if int(trace_meta.get("focus_point_count", 0) or 0) > 0:
                return "focus_point_miss"
            return "under_identification"

        if decision in {"false_positive", "rejected"}:
            if retrieval_hit_count > 0 and findings_count > 0:
                return "evidence_interpretation_error"
            if findings_count > 0:
                return "over_inference"
            return "wrong_severity"

        if "依据" in feedback_text and ("不匹配" in feedback_text or "不对" in feedback_text or "错误" in feedback_text):
            return "missing_regulatory_basis"
        if "不可执行" in feedback_text or "太空" in feedback_text or "进一步说明" in feedback_text:
            return "wording_not_actionable"
        if "漏" in feedback_text and int(trace_meta.get("focus_point_count", 0) or 0) > 0:
            return "focus_point_miss"
        if retrieval_hit_count <= 0:
            return "query_miss"
        return ""

    @staticmethod
    def _infer_confidence(feedback_record: Dict[str, object], trace_meta: Dict[str, object], sub_category: str) -> float:
        score = 0.4
        if feedback_record.get("labels"):
            score += 0.2
        if sub_category:
            score += 0.15
        if trace_meta.get("effective_queries"):
            score += 0.1
        if trace_meta.get("error_breakdown"):
            score += 0.1
        if trace_meta.get("retrieved_material_titles"):
            score += 0.05
        return min(score, 0.95)

    def classify_rag_issue(self, feedback_record: Dict[str, object], trace_meta: Dict[str, object], sub_category: str) -> str | None:
        if sub_category in self.RETRIEVAL_SUBCATEGORIES:
            return "rag_issue"
        if str(feedback_record.get("decision", "") or "") in {"missed", "missing_risk"} and int(trace_meta.get("retrieval_hit_count", 0) or 0) == 0:
            return "rag_issue"
        return None

    def classify_agent_issue(self, feedback_record: Dict[str, object], trace_meta: Dict[str, object], sub_category: str) -> str | None:
        if sub_category in self.AGENT_SUBCATEGORIES:
            return "agent_issue"
        return None

    def classify_prompt_issue(self, feedback_record: Dict[str, object], trace_meta: Dict[str, object], sub_category: str) -> str | None:
        if sub_category in self.PROMPT_SUBCATEGORIES:
            return "prompt_issue"
        return None

    def classify_rule_issue(self, feedback_record: Dict[str, object], trace_meta: Dict[str, object], sub_category: str) -> str | None:
        if sub_category in self.RULE_SUBCATEGORIES:
            return "rule_issue"
        return None
