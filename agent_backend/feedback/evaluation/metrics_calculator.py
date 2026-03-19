from __future__ import annotations

from typing import Any, Dict, List


class MetricsCalculator:
    """Calculate retrieval and review metrics for replay/evaluation outputs."""

    def calc_retrieval_metrics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate retrieval metrics from replay results."""
        return {"case_count": len(results), "retrieval_coverage": 0.0}

    def calc_review_metrics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate review metrics from replay results."""
        return {"case_count": len(results), "review_accuracy": 0.0}

    def calc_feedback_metrics(self, feedback_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate aggregate feedback metrics."""
        return {"feedback_count": len(feedback_records)}

    def calc_version_gain(self, old_results: List[Dict[str, Any]], new_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compare evaluation results across versions."""
        return {"old_count": len(old_results), "new_count": len(new_results)}
