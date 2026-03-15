from flask import Blueprint, request

from agent.agent_backend.agentic_rl.model_evaluation import evaluate_model
from agent.agent_backend.agentic_rl.reward_functions import feedback_metrics
from agent.agent_backend.utils.common_util import ResponseMessage


rl_bp = Blueprint("rl_controller", __name__, url_prefix="/rl")


@rl_bp.post("/health")
def health():
    print("[DEBUG] enter health | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    return ResponseMessage(200, "ok", {"ok": True}).to_json()


@rl_bp.post("/feedback-metrics")
def calc_feedback_metrics():
    print("[DEBUG] enter calc_feedback_metrics | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    payload = request.get_json(silent=True) or {}
    feedback_types = payload.get("feedback_types", [])
    if not isinstance(feedback_types, list):
        return ResponseMessage(400, "feedback_types must be list[str]", None).to_json(), 400
    metrics = feedback_metrics([str(x) for x in feedback_types])
    return ResponseMessage(200, "success", metrics).to_json()


@rl_bp.post("/evaluate")
def evaluate_predictions():
    print("[DEBUG] enter evaluate_predictions | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    payload = request.get_json(silent=True) or {}
    predictions = payload.get("predictions", [])
    references = payload.get("references", [])
    if not isinstance(predictions, list) or not isinstance(references, list):
        return ResponseMessage(400, "predictions/references must be list[str]", None).to_json(), 400
    result = evaluate_model(
        predictions=[str(x) for x in predictions],
        references=[str(x) for x in references],
    )
    return ResponseMessage(200, "success", result).to_json()
