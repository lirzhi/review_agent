import json
import time

from flask import Blueprint, request, Response, stream_with_context

from agent.agent_backend.services.knowledge_service import KnowledgeService
from agent.agent_backend.utils.common_util import ResponseMessage


knowledge_bp = Blueprint("knowledge_controller", __name__, url_prefix="/knowledge")
_knowledge_service: KnowledgeService | None = None


def get_knowledge_service() -> KnowledgeService:
    global _knowledge_service
    if _knowledge_service is None:
        _knowledge_service = KnowledgeService()
    return _knowledge_service


@knowledge_bp.post("/upload")
def upload_knowledge():
    print("[DEBUG] enter upload_knowledge | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    if "file" not in request.files:
        return ResponseMessage(400, "file is required", None).to_json(), 400
    file_obj = request.files["file"]
    classification = request.form.get("classification", "other")
    affect_range = request.form.get("affect_range", "other")
    ok, msg, data = get_knowledge_service().upload_knowledge(file_obj, classification, affect_range)
    if not ok:
        return ResponseMessage(400, msg, None).to_json(), 400
    return ResponseMessage(200, msg, data).to_json()


@knowledge_bp.post("/<doc_id>")
def update_knowledge(doc_id: str):
    print("[DEBUG] enter update_knowledge | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    payload = request.get_json(silent=True) or {}
    ok, msg = get_knowledge_service().update_knowledge(doc_id, payload)
    if not ok:
        return ResponseMessage(400, msg, None).to_json(), 400
    return ResponseMessage(200, msg, {"doc_id": doc_id}).to_json()


@knowledge_bp.post("/<doc_id>/delete")
def delete_knowledge(doc_id: str):
    print("[DEBUG] enter delete_knowledge | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    ok, msg = get_knowledge_service().delete_knowledge(doc_id)
    if not ok:
        return ResponseMessage(400, msg, None).to_json(), 400
    return ResponseMessage(200, msg, {"doc_id": doc_id}).to_json()


@knowledge_bp.post("/query")
def query_knowledge():
    print("[DEBUG] enter query_knowledge | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    payload = request.get_json(silent=True) or {}
    page = payload.get("page", 1)
    page_size = payload.get("page_size", 10)
    try:
        page = int(page)
        page_size = int(page_size)
    except Exception:
        return ResponseMessage(400, "page/page_size must be integer", None).to_json(), 400
    if page <= 0 or page_size <= 0:
        return ResponseMessage(400, "page/page_size must be > 0", None).to_json(), 400

    data = get_knowledge_service().query_knowledge(
        file_name=str(payload.get("file_name", "")),
        keyword=str(payload.get("keyword", "")),
        file_type=str(payload.get("file_type", "")),
        classification=str(payload.get("classification", "")),
        start_time=str(payload.get("start_time", "")),
        end_time=str(payload.get("end_time", "")),
        page=page,
        page_size=page_size,
    )
    return ResponseMessage(200, "success", data).to_json()


@knowledge_bp.post("/semantic-query")
def semantic_query():
    print("[DEBUG] enter semantic_query | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    payload = request.get_json(silent=True) or {}
    query = str(payload.get("query", "")).strip()
    if not query:
        return ResponseMessage(400, "query is required", None).to_json(), 400
    try:
        top_k = int(payload.get("top_k", 10))
    except Exception:
        return ResponseMessage(400, "top_k must be integer", None).to_json(), 400
    if top_k <= 0:
        return ResponseMessage(400, "top_k must be > 0", None).to_json(), 400
    try:
        min_score = float(payload.get("min_score", 0.6))
    except Exception:
        return ResponseMessage(400, "min_score must be number", None).to_json(), 400
    classification = str(payload.get("classification", "")).strip()
    data = get_knowledge_service().semantic_query(
        query,
        top_k,
        classification=classification,
        min_score=min_score,
    )
    return ResponseMessage(200, "success", data).to_json()


@knowledge_bp.post("/parse-progress")
def parse_progress():
    payload = request.get_json(silent=True) or {}
    doc_id = str(payload.get("doc_id", "")).strip()
    data = get_knowledge_service().get_parse_progress(doc_id=doc_id)
    return ResponseMessage(200, "success", data).to_json()


@knowledge_bp.post("/<doc_id>/parse")
def parse_knowledge(doc_id: str):
    ok, msg, data = get_knowledge_service().submit_parse(doc_id)
    if not ok:
        return ResponseMessage(400, msg, None).to_json(), 400
    return ResponseMessage(200, msg, data).to_json()


@knowledge_bp.get("/parse-progress/stream")
def parse_progress_stream():
    doc_id = str(request.args.get("doc_id", "")).strip()
    try:
        max_seconds = int(request.args.get("max_seconds", "300"))
    except Exception:
        max_seconds = 300
    max_seconds = max(15, min(max_seconds, 3600))

    def _gen():
        last_text = ""
        started = time.time()
        while True:
            data = get_knowledge_service().get_parse_progress(doc_id=doc_id)
            text = json.dumps(data, ensure_ascii=False)
            if text != last_text:
                last_text = text
                yield f"event: progress\ndata: {text}\n\n"
                if doc_id:
                    tasks = data.get("tasks", []) if isinstance(data, dict) else []
                    if tasks and isinstance(tasks[0], dict) and tasks[0].get("status") in {"completed", "failed"}:
                        break
            else:
                yield "event: ping\ndata: {}\n\n"
            if time.time() - started >= max_seconds:
                break
            time.sleep(1)

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return Response(stream_with_context(_gen()), mimetype="text/event-stream", headers=headers)
