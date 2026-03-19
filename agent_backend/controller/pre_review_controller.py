import json
import logging
import queue
import threading
import time

from flask import Blueprint, Response, request, send_file, stream_with_context

from agent.agent_backend.application.feedback_app_service import FeedbackAppService
from agent.agent_backend.services.pre_review_service import PreReviewService
from agent.agent_backend.utils.common_util import ResponseMessage


pre_review_bp = Blueprint("pre_review_controller", __name__, url_prefix="/pre-review")
_service: PreReviewService | None = None
_feedback_app_service: FeedbackAppService | None = None
_CONTROLLER_DEBUG_ONCE_KEYS: set[str] = set()


def _debug_once(key: str, message: str) -> None:
    if key in _CONTROLLER_DEBUG_ONCE_KEYS:
        return
    _CONTROLLER_DEBUG_ONCE_KEYS.add(key)
    print(message)


def get_pre_review_service() -> PreReviewService:
    global _service
    if _service is None:
        _debug_once("get_pre_review_service:init", "[DEBUG] enter get_pre_review_service | core: {}")
        _service = PreReviewService()
    return _service


def get_feedback_app_service() -> FeedbackAppService:
    global _feedback_app_service
    if _feedback_app_service is None:
        _feedback_app_service = FeedbackAppService()
    return _feedback_app_service


@pre_review_bp.post("/projects")
def create_project():
    print("[DEBUG] enter create_project | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    payload = request.get_json(silent=True) or {}
    ok, msg, data = get_pre_review_service().create_project(
        project_name=payload.get("project_name", ""),
        description=payload.get("description", ""),
        owner=payload.get("owner", ""),
        registration_scope=payload.get("registration_scope", ""),
        registration_path=payload.get("registration_path", []) if isinstance(payload.get("registration_path", []), list) else [],
        registration_leaf=payload.get("registration_leaf", ""),
        registration_description=payload.get("registration_description", ""),
    )
    if not ok:
        return ResponseMessage(400, msg, None).to_json(), 400
    return ResponseMessage(200, msg, data).to_json()


@pre_review_bp.post("/projects/<project_id>/delete")
def delete_project(project_id: str):
    print("[DEBUG] enter delete_project | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    ok, msg = get_pre_review_service().delete_project(project_id)
    if not ok:
        return ResponseMessage(400, msg, None).to_json(), 400
    return ResponseMessage(200, msg, {"project_id": project_id}).to_json()


@pre_review_bp.post("/projects/list")
def list_projects():
    print("[DEBUG] enter list_projects | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    payload = request.get_json(silent=True) or {}
    try:
        page = int(payload.get("page", 1))
        page_size = int(payload.get("page_size", 10))
    except Exception:
        return ResponseMessage(400, "page/page_size must be integer", None).to_json(), 400
    if page <= 0 or page_size <= 0:
        return ResponseMessage(400, "page/page_size must be > 0", None).to_json(), 400

    data = get_pre_review_service().list_projects(
        page=page,
        page_size=page_size,
        status=str(payload.get("status", "")),
    )
    return ResponseMessage(200, "success", data).to_json()


@pre_review_bp.post("/projects/<project_id>/detail")
def project_detail(project_id: str):
    print("[DEBUG] enter project_detail | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    ok, msg, data = get_pre_review_service().get_project_detail(project_id)
    if not ok:
        return ResponseMessage(404, msg, None).to_json(), 404
    return ResponseMessage(200, msg, data).to_json()


@pre_review_bp.post("/projects/<project_id>/submissions/upload")
def upload_submission(project_id: str):
    print("[DEBUG] enter upload_submission | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    files = request.files.getlist("files")
    if not files and "file" in request.files:
        files = [request.files["file"]]
    if not files:
        return ResponseMessage(400, "file is required", None).to_json(), 400
    material_category = str(request.form.get("material_category", "other") or "other")
    section_id = str(request.form.get("section_id", "") or "")
    upload_mode = str(request.form.get("mode", "") or "")
    out_items = []
    for file_obj in files:
        ok, msg, data = get_pre_review_service().upload_submission(
            project_id,
            file_obj,
            material_category=material_category,
            section_id=section_id,
            upload_mode=upload_mode,
        )
        if not ok:
            status = 404 if "not found" in msg.lower() else 400
            return ResponseMessage(status, msg, None).to_json(), status
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            out_items.extend(data.get("items", []))
        elif data is not None:
            out_items.append(data)
    return ResponseMessage(200, "submission uploaded", {"items": out_items, "count": len(out_items)}).to_json()


@pre_review_bp.post("/projects/<project_id>/ctd-catalog")
def project_ctd_catalog(project_id: str):
    print("[DEBUG] enter project_ctd_catalog | core:", {"project_id": project_id})
    data = get_pre_review_service().get_ctd_section_catalog(project_id=project_id)
    return ResponseMessage(200, "success", data).to_json()


@pre_review_bp.post("/projects/<project_id>/submissions/list")
def list_submissions(project_id: str):
    print("[DEBUG] enter list_submissions | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    payload = request.get_json(silent=True) or {}
    try:
        page = int(payload.get("page", 1))
        page_size = int(payload.get("page_size", 20))
    except Exception:
        return ResponseMessage(400, "page/page_size must be integer", None).to_json(), 400
    if page <= 0 or page_size <= 0:
        return ResponseMessage(400, "page/page_size must be > 0", None).to_json(), 400
    data = get_pre_review_service().list_submissions(project_id=project_id, page=page, page_size=page_size)
    return ResponseMessage(200, "success", data).to_json()


@pre_review_bp.post("/projects/<project_id>/submissions/<doc_id>/content")
def submission_content(project_id: str, doc_id: str):
    print("[DEBUG] enter submission_content | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    ok, msg, data = get_pre_review_service().get_submission_content(project_id=project_id, doc_id=doc_id)
    if not ok:
        status = 404 if "not found" in msg.lower() else 400
        return ResponseMessage(status, msg, None).to_json(), status
    return ResponseMessage(200, msg, data).to_json()


@pre_review_bp.post("/projects/<project_id>/submissions/<doc_id>/content/save")
def save_submission_content(project_id: str, doc_id: str):
    payload = request.get_json(silent=True) or {}
    ok, msg, data = get_pre_review_service().save_submission_content(
        project_id=project_id,
        doc_id=doc_id,
        content=str(payload.get("content", "") or ""),
    )
    if not ok:
        status = 404 if "not found" in msg.lower() else 400
        return ResponseMessage(status, msg, None).to_json(), status
    return ResponseMessage(200, msg, data).to_json()


@pre_review_bp.post("/projects/<project_id>/ctd-sections/<section_id>/concerns")
def update_section_concerns(project_id: str, section_id: str):
    payload = request.get_json(silent=True) or {}
    concern_points = payload.get("concern_points", []) if isinstance(payload.get("concern_points", []), list) else []
    ok, msg, data = get_pre_review_service().update_section_concerns(
        project_id=project_id,
        section_id=section_id,
        concern_points=concern_points,
    )
    if not ok:
        status = 404 if "not found" in msg.lower() else 400
        return ResponseMessage(status, msg, None).to_json(), status
    return ResponseMessage(200, msg, data).to_json()


@pre_review_bp.post("/projects/<project_id>/submissions/<doc_id>/sections")
def submission_sections(project_id: str, doc_id: str):
    print("[DEBUG] enter submission_sections | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    ok, msg, data = get_pre_review_service().get_submission_sections(project_id=project_id, doc_id=doc_id)
    if not ok:
        status = 404 if "not found" in msg.lower() else 400
        return ResponseMessage(status, msg, None).to_json(), status
    return ResponseMessage(200, msg, data).to_json()


@pre_review_bp.post("/projects/<project_id>/submissions/<doc_id>/sections/<section_id>/replay")
def replay_submission_section(project_id: str, doc_id: str, section_id: str):
    print("[DEBUG] enter replay_submission_section | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    payload = request.get_json(silent=True) or {}
    run_config = payload.get("run_config", {}) if isinstance(payload.get("run_config", {}), dict) else {}
    ok, msg, data = get_pre_review_service().run_section_replay(
        project_id=project_id,
        source_doc_id=doc_id,
        section_id=section_id,
        run_config=run_config,
    )
    if not ok:
        status = 404 if "not found" in msg.lower() else 400
        return ResponseMessage(status, msg, None).to_json(), status
    return ResponseMessage(200, msg, data).to_json()


@pre_review_bp.get("/projects/<project_id>/submissions/<doc_id>/preview")
def submission_preview(project_id: str, doc_id: str):
    print("[DEBUG] enter submission_preview | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    ok, msg, data = get_pre_review_service().get_submission_file_info(project_id=project_id, doc_id=doc_id)
    if not ok:
        status = 404 if "not found" in msg.lower() else 400
        return ResponseMessage(status, msg, None).to_json(), status
    return send_file(
        data["file_path"],
        as_attachment=False,
        download_name=data["file_name"],
        conditional=True,
    )


@pre_review_bp.post("/runs")
def run_pre_review():
    print("[DEBUG] enter run_pre_review | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    payload = request.get_json(silent=True) or {}
    project_id = (
        str(payload.get("project_id", "")).strip()
        or str(payload.get("projectId", "")).strip()
    )
    source_doc_id = (
        str(payload.get("source_doc_id", "")).strip()
        or str(payload.get("sourceDocId", "")).strip()
        or str(payload.get("doc_id", "")).strip()
        or str(payload.get("docId", "")).strip()
    )
    if not project_id or not source_doc_id:
        logging.warning(
            "run_pre_review missing required fields. payload_keys=%s",
            list(payload.keys()),
        )
        return ResponseMessage(400, "project_id and source_doc_id are required", None).to_json(), 400

    run_config = payload.get("run_config", {}) if isinstance(payload.get("run_config", {}), dict) else {}
    ok, msg, data = get_pre_review_service().run_pre_review(project_id, source_doc_id, run_config=run_config)
    if not ok:
        logging.warning(
            "run_pre_review failed. project_id=%s source_doc_id=%s msg=%s",
            project_id,
            source_doc_id,
            msg,
        )
        status = 404 if "not found" in msg.lower() else 400
        return ResponseMessage(status, msg, None).to_json(), status
    return ResponseMessage(200, msg, data).to_json()


@pre_review_bp.post("/runs/history")
def run_history():
    print("[DEBUG] enter run_history | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    payload = request.get_json(silent=True) or {}
    project_id = str(payload.get("project_id", ""))
    if not project_id:
        return ResponseMessage(400, "project_id is required", None).to_json(), 400
    data = get_pre_review_service().get_run_history(project_id)
    return ResponseMessage(200, "success", data).to_json()


@pre_review_bp.post("/dashboard")
def dashboard_summary():
    print("[DEBUG] enter dashboard_summary | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    data = get_pre_review_service().get_dashboard_summary()
    return ResponseMessage(200, "success", data).to_json()


@pre_review_bp.post("/runs/<run_id>/sections")
def get_sections(run_id: str):
    print("[DEBUG] enter get_sections | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    payload = request.get_json(silent=True) or {}
    section_id = str(payload.get("section_id", ""))
    data = get_pre_review_service().get_section_conclusions(run_id, section_id)
    return ResponseMessage(200, "success", data).to_json()


@pre_review_bp.post("/runs/<run_id>/sections/overview")
def get_sections_overview(run_id: str):
    print("[DEBUG] enter get_sections_overview | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    ok, msg, data = get_pre_review_service().get_run_section_overview(run_id=run_id)
    if not ok:
        status = 404 if "not found" in msg.lower() else 400
        return ResponseMessage(status, msg, None).to_json(), status
    return ResponseMessage(200, msg, data).to_json()


@pre_review_bp.post("/runs/<run_id>/traces")
def get_traces(run_id: str):
    print("[DEBUG] enter get_traces | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    payload = request.get_json(silent=True) or {}
    section_id = str(payload.get("section_id", ""))
    data = get_pre_review_service().get_section_traces(run_id, section_id)
    return ResponseMessage(200, "success", data).to_json()


@pre_review_bp.post("/runs/<run_id>/patches")
def get_patches(run_id: str):
    print("[DEBUG] enter get_patches | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    payload = request.get_json(silent=True) or {}
    section_id = str(payload.get("section_id", "") or "")
    ok, msg, data = get_pre_review_service().get_section_patch_candidates(run_id=run_id, section_id=section_id)
    if not ok:
        status = 404 if "not found" in msg.lower() else 400
        return ResponseMessage(status, msg, None).to_json(), status
    return ResponseMessage(200, msg, data).to_json()


@pre_review_bp.get("/runs/stream")
def run_pre_review_stream():
    project_id = str(request.args.get("project_id", "")).strip()
    source_doc_id = str(request.args.get("source_doc_id", "")).strip()
    if not project_id or not source_doc_id:
        return ResponseMessage(400, "project_id and source_doc_id are required", None).to_json(), 400

    run_config_raw = str(request.args.get("run_config", "") or "").strip()
    try:
        run_config = json.loads(run_config_raw) if run_config_raw else {}
    except Exception:
        return ResponseMessage(400, "run_config must be valid JSON", None).to_json(), 400
    if not isinstance(run_config, dict):
        return ResponseMessage(400, "run_config must be a JSON object", None).to_json(), 400
    try:
        max_seconds = int(request.args.get("max_seconds", "900"))
    except Exception:
        max_seconds = 900
    max_seconds = max(30, min(max_seconds, 7200))

    event_queue: "queue.Queue[dict]" = queue.Queue()
    finished = threading.Event()

    def _emit_progress(event_payload: dict) -> None:
        event_queue.put({"event": "progress", "data": event_payload})

    def _worker() -> None:
        try:
            ok, msg, data = get_pre_review_service().run_pre_review(
                project_id,
                source_doc_id,
                run_config=run_config,
                progress_callback=_emit_progress,
            )
            event_queue.put(
                {
                    "event": "done" if ok else "error",
                    "data": {
                        "ok": ok,
                        "message": msg,
                        "data": data,
                        "project_id": project_id,
                        "source_doc_id": source_doc_id,
                    },
                }
            )
        except Exception as exc:
            event_queue.put(
                {
                    "event": "error",
                    "data": {
                        "ok": False,
                        "message": str(exc),
                        "project_id": project_id,
                        "source_doc_id": source_doc_id,
                    },
                }
            )
        finally:
            finished.set()

    @stream_with_context
    def _gen():
        worker = threading.Thread(target=_worker, name=f"pre-review-sse-{project_id}", daemon=True)
        worker.start()
        started = time.time()
        while True:
            try:
                item = event_queue.get(timeout=1.0)
                yield f"event: {item['event']}\ndata: {json.dumps(item['data'], ensure_ascii=False)}\n\n"
                if finished.is_set() and event_queue.empty():
                    break
            except queue.Empty:
                yield "event: ping\ndata: {}\n\n"
                if finished.is_set() and event_queue.empty():
                    break
                if time.time() - started >= max_seconds:
                    timeout_payload = {
                        "ok": False,
                        "message": "stream timeout",
                        "project_id": project_id,
                        "source_doc_id": source_doc_id,
                    }
                    yield f"event: error\ndata: {json.dumps(timeout_payload, ensure_ascii=False)}\n\n"
                    break

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return Response(_gen(), mimetype="text/event-stream", headers=headers)


@pre_review_bp.post("/runs/<run_id>/export")
def export_report(run_id: str):
    print("[DEBUG] enter export_report | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    ok, msg, path = get_pre_review_service().export_report_word(run_id)
    if not ok:
        return ResponseMessage(400, msg, None).to_json(), 400
    return ResponseMessage(200, msg, {"run_id": run_id, "report_path": path}).to_json()


@pre_review_bp.post("/runs/<run_id>/feedback")
def add_feedback(run_id: str):
    print("[DEBUG] enter add_feedback | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    payload = request.get_json(silent=True) or {}
    feedback_type = str(payload.get("feedback_type", "") or "").strip().lower()
    if not feedback_type:
        decision = str(payload.get("decision", "") or "").strip().lower()
        if decision in {"false_positive", "invalid", "rejected"}:
            feedback_type = "false_positive"
        elif decision in {"missed", "missing_risk"}:
            feedback_type = "missed"
        else:
            feedback_type = "valid"
    ok, msg, data = get_pre_review_service().add_feedback(
        run_id=run_id,
        section_id=payload.get("section_id", ""),
        feedback_type=feedback_type,
        feedback_text=payload.get("feedback_text", ""),
        suggestion=payload.get("suggestion", ""),
        operator=payload.get("operator", ""),
        feedback_meta={
            "chain_mode": str(payload.get("chain_mode", "") or "feedback_only"),
            "decision": str(payload.get("decision", "") or ""),
            "manual_modified": bool(payload.get("manual_modified", False)),
            "feedback_type": feedback_type,
            "persist_event": True,
        },
    )
    if not ok:
        return ResponseMessage(400, msg, None).to_json(), 400
    return ResponseMessage(200, msg, {"run_id": run_id, "stats": data}).to_json()


@pre_review_bp.post("/runs/<run_id>/feedback/optimize")
def optimize_feedback(run_id: str):
    print("[DEBUG] enter optimize_feedback | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    payload = request.get_json(silent=True) or {}
    feedback_payload = {
        "run_id": run_id,
        "section_id": str(payload.get("section_id", "") or ""),
        "decision": str(payload.get("decision", "") or ""),
        "chain_mode": str(payload.get("chain_mode", "") or "feedback_optimize"),
        "manual_modified": bool(payload.get("manual_modified", False)),
        "labels": payload.get("labels", []) if isinstance(payload.get("labels", []), list) else [],
        "issue_feedback": payload.get("issue_feedback", []) if isinstance(payload.get("issue_feedback", []), list) else [],
        "paragraph_feedback": payload.get("paragraph_feedback", []) if isinstance(payload.get("paragraph_feedback", []), list) else [],
        "evidence_feedback": payload.get("evidence_feedback", []) if isinstance(payload.get("evidence_feedback", []), list) else [],
        "original_output": payload.get("original_output", {}),
        "revised_output": payload.get("revised_output", {}),
        "feedback_text": str(payload.get("feedback_text", "") or ""),
        "suggestion": str(payload.get("suggestion", "") or ""),
        "operator": str(payload.get("operator", "") or ""),
    }
    result = get_feedback_app_service().submit_feedback(feedback_payload)
    if not bool(result.get("success", False)):
        return ResponseMessage(400, str(result.get("message", "feedback optimize failed")), result.get("data")).to_json(), 400
    return ResponseMessage(200, str(result.get("message", "feedback optimize completed")), result.get("data")).to_json()


@pre_review_bp.post("/runs/<run_id>/feedback/stats")
def feedback_stats(run_id: str):
    print("[DEBUG] enter feedback_stats | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    payload = request.get_json(silent=True) or {}
    section_id = str(payload.get("section_id", ""))
    ok, msg, data = get_pre_review_service().get_feedback_stats(run_id=run_id, section_id=section_id)
    if not ok:
        return ResponseMessage(400, msg, None).to_json(), 400
    return ResponseMessage(200, msg, data).to_json()


@pre_review_bp.post("/prompt-versions/list")
def list_prompt_versions():
    result = get_feedback_app_service().list_prompt_versions()
    return ResponseMessage(200, str(result.get("message", "success")), result.get("data")).to_json()


@pre_review_bp.post("/prompt-versions/<version_id>/activate")
def activate_prompt_version(version_id: str):
    try:
        result = get_feedback_app_service().activate_prompt_version(version_id)
    except FileNotFoundError as exc:
        return ResponseMessage(404, str(exc), None).to_json(), 404
    return ResponseMessage(200, str(result.get("message", "prompt version activated")), result.get("data")).to_json()


@pre_review_bp.post("/prompt-versions/rollback")
def rollback_prompt_version():
    result = get_feedback_app_service().rollback_prompt_version()
    return ResponseMessage(200, str(result.get("message", "prompt version rolled back")), result.get("data")).to_json()
