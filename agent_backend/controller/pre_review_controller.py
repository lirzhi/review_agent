import logging

from flask import Blueprint, request, send_file

from agent.agent_backend.services.pre_review_service import PreReviewService
from agent.agent_backend.utils.common_util import ResponseMessage


pre_review_bp = Blueprint("pre_review_controller", __name__, url_prefix="/pre-review")
_service: PreReviewService | None = None


def get_pre_review_service() -> PreReviewService:
    print("[DEBUG] enter get_pre_review_service | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    global _service
    if _service is None:
        _service = PreReviewService()
    return _service


@pre_review_bp.post("/projects")
def create_project():
    print("[DEBUG] enter create_project | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    payload = request.get_json(silent=True) or {}
    ok, msg, data = get_pre_review_service().create_project(
        project_name=payload.get("project_name", ""),
        description=payload.get("description", ""),
        owner=payload.get("owner", ""),
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
    if "file" not in request.files:
        return ResponseMessage(400, "file is required", None).to_json(), 400
    ok, msg, data = get_pre_review_service().upload_submission(project_id, request.files["file"])
    if not ok:
        status = 404 if "not found" in msg.lower() else 400
        return ResponseMessage(status, msg, None).to_json(), status
    return ResponseMessage(200, msg, data).to_json()


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


@pre_review_bp.post("/projects/<project_id>/submissions/<doc_id>/sections")
def submission_sections(project_id: str, doc_id: str):
    print("[DEBUG] enter submission_sections | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    ok, msg, data = get_pre_review_service().get_submission_sections(project_id=project_id, doc_id=doc_id)
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

    ok, msg, data = get_pre_review_service().run_pre_review(project_id, source_doc_id)
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


@pre_review_bp.post("/agents/roles")
def agent_roles():
    print("[DEBUG] enter agent_roles | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    data = get_pre_review_service().get_agent_roles()
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
    ok, msg, data = get_pre_review_service().add_feedback(
        run_id=run_id,
        section_id=payload.get("section_id", ""),
        feedback_type=payload.get("feedback_type", ""),
        feedback_text=payload.get("feedback_text", ""),
        suggestion=payload.get("suggestion", ""),
        operator=payload.get("operator", ""),
    )
    if not ok:
        return ResponseMessage(400, msg, None).to_json(), 400
    return ResponseMessage(200, msg, {"run_id": run_id, "stats": data}).to_json()


@pre_review_bp.post("/runs/<run_id>/feedback/stats")
def feedback_stats(run_id: str):
    print("[DEBUG] enter feedback_stats | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    payload = request.get_json(silent=True) or {}
    section_id = str(payload.get("section_id", ""))
    ok, msg, data = get_pre_review_service().get_feedback_stats(run_id=run_id, section_id=section_id)
    if not ok:
        return ResponseMessage(400, msg, None).to_json(), 400
    return ResponseMessage(200, msg, data).to_json()
