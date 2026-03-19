from __future__ import annotations

from typing import Any, Dict

from agent.agent_backend.feedback.collection.diff_extractor import DiffExtractor
from agent.agent_backend.feedback.collection.feedback_validator import FeedbackValidator


class FeedbackIngestor:
    """Normalize and enrich feedback payloads before routing."""

    def __init__(self) -> None:
        self.validator = FeedbackValidator()
        self.diff_extractor = DiffExtractor()

    def ingest(self, feedback_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Validate, normalize, and attach run context."""
        self.validator.validate(feedback_payload)
        normalized = self.normalize_feedback(feedback_payload)
        with_context = self.attach_run_context(normalized)
        diff = self.diff_extractor.extract_diff(
            str(with_context.get("original_output", "") or ""),
            str(with_context.get("revised_output", "") or ""),
        )
        with_context["diff_result"] = diff
        return with_context

    def normalize_feedback(self, feedback_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize minimal feedback payload into stable dict fields."""
        decision = str(feedback_payload.get("decision", "") or "").strip().lower()
        labels = [str(x).strip().lower() for x in list(feedback_payload.get("labels", []) or []) if str(x).strip()]
        return {
            "run_id": str(feedback_payload.get("run_id", "") or ""),
            "section_id": str(feedback_payload.get("section_id", "") or ""),
            "decision": decision,
            "labels": labels,
            "chain_mode": str(feedback_payload.get("chain_mode", "") or "").strip() or "feedback_optimize",
            "manual_modified": bool(feedback_payload.get("manual_modified", False)),
            "issue_feedback": list(feedback_payload.get("issue_feedback", []) or []),
            "paragraph_feedback": list(feedback_payload.get("paragraph_feedback", []) or []),
            "evidence_feedback": list(feedback_payload.get("evidence_feedback", []) or []),
            "original_output": feedback_payload.get("original_output", {}),
            "revised_output": feedback_payload.get("revised_output", {}),
            "feedback_text": str(feedback_payload.get("feedback_text", "") or ""),
            "suggestion": str(feedback_payload.get("suggestion", "") or ""),
            "operator": str(feedback_payload.get("operator", "") or ""),
        }

    def attach_run_context(self, feedback_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Attach minimal context fields for downstream processors."""
        payload = dict(feedback_payload)
        payload["context"] = {
            "run_id": payload.get("run_id", ""),
            "section_id": payload.get("section_id", ""),
        }
        return payload

    def persist_feedback(self, feedback_record: Dict[str, Any]) -> str:
        """Return a stable feedback identifier. Persistence is delegated upstream."""
        return f"{feedback_record.get('run_id', 'run')}:{feedback_record.get('section_id', 'global')}"
