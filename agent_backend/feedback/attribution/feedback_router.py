from __future__ import annotations

from typing import Dict, List


class FeedbackRouter:
    """Route attributed feedback into optimization channels."""

    def route(self, feedback_record: Dict[str, object], root_cause: Dict[str, object]) -> List[str]:
        """Return downstream routes for one feedback record."""
        category = str(root_cause.get("root_category", "") or "")
        decision = str(feedback_record.get("decision", "") or "")
        if category == "rag_issue":
            return ["retrieval_fix", "rerank_dataset", "regression_case"]
        if category == "rule_issue":
            return ["rule_fix", "regression_case"]
        if category == "prompt_issue":
            return ["prompt_fix", "preference_dataset", "regression_case"]
        if category == "agent_issue":
            return ["workflow_fix", "preference_dataset", "regression_case"] if decision != "valid" else ["regression_case"]
        if category == "workflow_issue":
            return ["workflow_fix", "regression_case"]
        return ["regression_case"]
