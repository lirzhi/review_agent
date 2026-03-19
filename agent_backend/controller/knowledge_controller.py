import json
import os
import shutil
import tempfile
import time
import zipfile

from flask import Blueprint, request, Response, stream_with_context

from agent.agent_backend.services.knowledge_service import KnowledgeService
from agent.agent_backend.utils.common_util import ResponseMessage


knowledge_bp = Blueprint("knowledge_controller", __name__, url_prefix="/knowledge")
_knowledge_service: KnowledgeService | None = None


def _decode_zip_member_name(raw_name: str) -> str:
    base_name = os.path.basename(str(raw_name or "")).strip()
    if not base_name:
        return ""
    # 兼容 Windows 常见的 zip 中文文件名编码：cp437 误解码自 gbk/gb18030。
    if any("\u2500" <= ch <= "\u257f" or "\u2580" <= ch <= "\u259f" for ch in base_name):
        for enc in ("gbk", "gb18030", "utf-8"):
            try:
                decoded = base_name.encode("cp437").decode(enc)
                if decoded:
                    return os.path.basename(decoded).strip()
            except Exception:
                continue
    return base_name


def get_knowledge_service() -> KnowledgeService:
    global _knowledge_service
    if _knowledge_service is None:
        _knowledge_service = KnowledgeService()
    return _knowledge_service


@knowledge_bp.post("/upload")
def upload_knowledge():
    print("[DEBUG] enter upload_knowledge | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    files = [f for f in request.files.getlist("files") if getattr(f, "filename", "")]
    if not files and "file" in request.files:
        file_obj = request.files["file"]
        if getattr(file_obj, "filename", ""):
            files = [file_obj]
    if not files:
        return ResponseMessage(400, "file is required", None).to_json(), 400
    classification = request.form.get("classification", "other")
    affect_range = request.form.get("affect_range", "other")
    profession_classification = request.form.get("profession_classification", "other")
    registration_scope = request.form.get("registration_scope", "other")
    registration_path = request.form.get("registration_path", "")
    experience_type = request.form.get("experience_type", "other")
    service = get_knowledge_service()
    supported_exts = {".pdf", ".doc", ".docx", ".txt", ".md"}
    uploaded_items = []
    failed_items = []

    def _handle_single_file(single_file):
        ok, msg, data = service.upload_knowledge(
            single_file,
            classification,
            affect_range,
            profession_classification,
            registration_scope,
            registration_path,
            experience_type,
        )
        if ok and data:
            uploaded_items.append(data)
        else:
            failed_items.append({
                "file_name": getattr(single_file, "filename", ""),
                "message": msg,
            })

    for file_obj in files:
        file_name = str(getattr(file_obj, "filename", "") or "")
        suffix = os.path.splitext(file_name)[1].lower()
        if suffix != ".zip":
            _handle_single_file(file_obj)
            continue

        try:
            raw_bytes = file_obj.read()
            file_obj.stream.seek(0)
            with tempfile.TemporaryDirectory(prefix="kb_zip_") as temp_dir:
                archive_path = os.path.join(temp_dir, file_name or "archive.zip")
                with open(archive_path, "wb") as archive_file:
                    archive_file.write(raw_bytes)
                with zipfile.ZipFile(archive_path, "r") as archive:
                    members = [m for m in archive.infolist() if not m.is_dir()]
                    extracted_any = False
                    for member in members:
                        member_name = _decode_zip_member_name(member.filename)
                        ext = os.path.splitext(member_name)[1].lower()
                        if not member_name or ext not in supported_exts:
                            continue
                        extracted_any = True
                        extracted_path = os.path.join(temp_dir, member_name)
                        with archive.open(member, "r") as src, open(extracted_path, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        ok, msg, data = service.upload_local_knowledge(
                            file_path=extracted_path,
                            file_name=member_name,
                            classification=classification,
                            affect_range=affect_range,
                            profession_classification=profession_classification,
                            registration_scope=registration_scope,
                            registration_path=registration_path,
                            experience_type=experience_type,
                        )
                        if ok and data:
                            uploaded_items.append(data)
                        else:
                            failed_items.append({
                                "file_name": member_name,
                                "message": msg,
                            })
                    if not extracted_any:
                        failed_items.append({
                            "file_name": file_name,
                            "message": "zip contains no supported files",
                        })
        except Exception as exc:
            failed_items.append({
                "file_name": file_name,
                "message": f"zip upload failed: {exc}",
            })

    if not uploaded_items:
        message = failed_items[0]["message"] if failed_items else "upload failed"
        return ResponseMessage(400, message, {
            "items": [],
            "failed": failed_items,
            "success_count": 0,
            "fail_count": len(failed_items),
        }).to_json(), 400

    response_data = {
        "items": uploaded_items,
        "failed": failed_items,
        "success_count": len(uploaded_items),
        "fail_count": len(failed_items),
    }
    if len(uploaded_items) == 1:
        response_data.update(uploaded_items[0])
    message = "upload completed"
    if failed_items:
        message = f"upload completed with {len(failed_items)} failures"
    return ResponseMessage(200, message, response_data).to_json()


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


@knowledge_bp.post("/batch-delete")
def batch_delete_knowledge():
    payload = request.get_json(silent=True) or {}
    doc_ids = payload.get("doc_ids", [])
    ok, msg, data = get_knowledge_service().delete_knowledge_batch(doc_ids if isinstance(doc_ids, list) else [])
    if not ok:
        return ResponseMessage(400, msg, data).to_json(), 400
    return ResponseMessage(200, msg, data).to_json()


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
        affect_range=str(payload.get("affect_range", "")),
        profession_classification=str(payload.get("profession_classification", "")),
        registration_scope=str(payload.get("registration_scope", "")),
        registration_path=str(payload.get("registration_path", "")),
        experience_type=str(payload.get("experience_type", "")),
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
        min_score = float(payload.get("min_score", 0.0))
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


@knowledge_bp.post("/<doc_id>/reindex")
def reindex_knowledge(doc_id: str):
    ok, msg, data = get_knowledge_service().submit_reindex(doc_id)
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
            try:
                data = get_knowledge_service().get_parse_progress(doc_id=doc_id)
            except Exception as exc:
                error_payload = {
                    "doc_id": doc_id,
                    "status": "failed",
                    "message": str(exc),
                    "tasks": [],
                }
                yield f"event: error\ndata: {json.dumps(error_payload, ensure_ascii=False)}\n\n"
                break
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
