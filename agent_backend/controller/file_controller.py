import json
import os
from typing import Any, Dict, List

from flask import Blueprint, request

from agent.agent_backend.config.settings import settings
from agent.agent_backend.services.file_service import FileService
from agent.agent_backend.utils.common_util import ResponseMessage
from agent.agent_backend.utils.parser import ParserManager


file_bp = Blueprint("file_controller", __name__)
_service: FileService | None = None
os.makedirs(settings.parse_dir, exist_ok=True)


def get_file_service() -> FileService:
    print("[DEBUG] enter get_file_service | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    global _service
    if _service is None:
        _service = FileService()
    return _service


@file_bp.post("/health")
def health():
    print("[DEBUG] enter health | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    return ResponseMessage(200, "ok", {"ok": True}).to_json()


@file_bp.post("/files/upload")
def upload_file():
    print("[DEBUG] enter upload_file | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    file_list = request.files.getlist("files")
    if not file_list and "file" in request.files:
        file_list = [request.files["file"]]
    if not file_list:
        return ResponseMessage(400, "file/files is required", None).to_json(), 400

    classification = request.form.get("classification", "other")
    affect_range = request.form.get("affect_range", "other")
    supported_exts = set(ParserManager.list_supported_extensions())

    success_items: List[Dict[str, Any]] = []
    failed_items: List[Dict[str, str]] = []
    for file_obj in file_list:
        filename = str(getattr(file_obj, "filename", "") or "")
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if not ext or ext not in supported_exts:
            failed_items.append(
                {
                    "file_name": filename,
                    "message": f"unsupported file type: {ext or 'unknown'} (supported: {sorted(supported_exts)})",
                }
            )
            continue
        ok, msg, data = get_file_service().upload_file(file_obj, classification=classification, affect_range=affect_range)
        if ok and data:
            success_items.append(data)
        else:
            failed_items.append({"file_name": filename, "message": msg})

    code = 200 if success_items else 400
    message = "upload success" if success_items and not failed_items else "upload partial success" if success_items else "upload failed"
    return ResponseMessage(
        code,
        message,
        {"success": success_items, "failed": failed_items, "success_count": len(success_items), "failed_count": len(failed_items)},
    ).to_json(), code


@file_bp.post("/files/add")
def add_file():
    print("[DEBUG] enter add_file | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    payload = request.get_json(silent=True) or {}
    file_path = str(payload.get("file_path", "")).strip()
    if not file_path:
        return ResponseMessage(400, "file_path is required", None).to_json(), 400
    ext = os.path.splitext(file_path)[1].lstrip(".").lower()
    if not ParserManager.is_supported(ext):
        return ResponseMessage(
            400,
            f"unsupported file type: {ext or 'unknown'} (supported: {ParserManager.list_supported_extensions()})",
            None,
        ).to_json(), 400

    ok, msg, data = get_file_service().add_file(
        file_path=file_path,
        file_name=payload.get("file_name", ""),
        classification=str(payload.get("classification", "other")),
        affect_range=str(payload.get("affect_range", "other")),
    )
    if not ok:
        return ResponseMessage(400, msg, None).to_json(), 400
    return ResponseMessage(200, msg, data).to_json()


@file_bp.post("/files")
def list_files():
    print("[DEBUG] enter list_files | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    payload = request.get_json(silent=True) or {}
    try:
        page = int(payload.get("page", 1))
        page_size = int(payload.get("page_size", 10))
    except Exception:
        return ResponseMessage(400, "page/page_size must be integer", None).to_json(), 400

    file_name = str(payload.get("file_name", "")).strip()
    doc_id = str(payload.get("doc_id", "")).strip()
    classification = str(payload.get("classification", "")).strip()

    if file_name:
        data = get_file_service().query_by_file_name(file_name, page=page, page_size=page_size)
    elif doc_id:
        data = get_file_service().query_by_doc_id(doc_id, page=page, page_size=page_size)
    elif classification:
        data = get_file_service().query_by_classification(classification, page=page, page_size=page_size)
    else:
        data = get_file_service().query_by_file_name("", page=page, page_size=page_size)
    return ResponseMessage(200, "success", data).to_json()


@file_bp.post("/files/<doc_id>/detail")
def get_file(doc_id: str):
    print("[DEBUG] enter get_file | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    data = get_file_service().get_file_by_doc_id(doc_id)
    if not data:
        return ResponseMessage(404, "file not found", None).to_json(), 404
    return ResponseMessage(200, "success", data).to_json()


@file_bp.post("/files/<doc_id>/update")
def update_file(doc_id: str):
    print("[DEBUG] enter update_file | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    payload = request.get_json(silent=True) or {}
    ok, msg = get_file_service().update_file(doc_id, payload)
    if not ok:
        return ResponseMessage(400, msg, None).to_json(), 400
    return ResponseMessage(200, msg, {"doc_id": doc_id}).to_json()


@file_bp.post("/files/<doc_id>/delete")
def delete_file(doc_id: str):
    print("[DEBUG] enter delete_file | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    ok, msg = get_file_service().delete_file(doc_id)
    if not ok:
        return ResponseMessage(404, msg, None).to_json(), 404
    return ResponseMessage(200, msg, {"doc_id": doc_id}).to_json()


@file_bp.post("/files/<doc_id>/chunk-status")
def update_chunk_status(doc_id: str):
    print("[DEBUG] enter update_chunk_status | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    payload = request.get_json(silent=True) or {}
    if "is_chunked" not in payload:
        return ResponseMessage(400, "is_chunked is required", None).to_json(), 400

    try:
        is_chunked = int(payload.get("is_chunked", 0))
        chunk_size = payload.get("chunk_size", None)
        chunk_size = None if chunk_size is None else int(chunk_size)
    except Exception:
        return ResponseMessage(400, "is_chunked/chunk_size must be integer", None).to_json(), 400

    ok, msg = get_file_service().update_chunk_status(
        doc_id=doc_id,
        is_chunked=is_chunked,
        chunk_ids=str(payload.get("chunk_ids", "")),
        chunk_size=chunk_size,
    )
    if not ok:
        return ResponseMessage(400, msg, None).to_json(), 400
    return ResponseMessage(200, msg, {"doc_id": doc_id}).to_json()


@file_bp.post("/files/<doc_id>/review-status")
def update_review_status(doc_id: str):
    print("[DEBUG] enter update_review_status | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    payload = request.get_json(silent=True) or {}
    if "review_status" not in payload:
        return ResponseMessage(400, "review_status is required", None).to_json(), 400
    try:
        review_status = int(payload["review_status"])
    except Exception:
        return ResponseMessage(400, "review_status must be integer", None).to_json(), 400

    ok, msg = get_file_service().update_review_status(doc_id, review_status)
    if not ok:
        return ResponseMessage(400, msg, None).to_json(), 400
    return ResponseMessage(200, msg, {"doc_id": doc_id, "review_status": review_status}).to_json()


@file_bp.post("/files/<doc_id>/parse")
def parse_file(doc_id: str):
    print("[DEBUG] enter parse_file | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    info = get_file_service().get_file_by_doc_id(doc_id)
    if not info:
        return ResponseMessage(404, "doc not found", None).to_json(), 404

    try:
        ext_hint = str(info.get("file_type", "") or "").strip()
        file_name = str(info.get("file_name", "") or "")
        if not ext_hint and "." in file_name:
            ext_hint = file_name.rsplit(".", 1)[-1].lower()
        chunks = ParserManager.parse(info["file_path"], ext_hint=ext_hint)
        parse_path = os.path.join(settings.parse_dir, f"{doc_id}.json")
        with open(parse_path, "w", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)

        chunk_ids = []
        for idx, item in enumerate(chunks):
            cid = str(item.get("chunk_id", idx + 1))
            chunk_ids.append(cid)
        chunk_id_str = ";".join(chunk_ids)
        ok, msg = get_file_service().update_chunk_status(
            doc_id=doc_id,
            is_chunked=1,
            chunk_ids=chunk_id_str,
            chunk_size=len(chunks),
        )
        if not ok:
            return ResponseMessage(500, f"parse succeeded but status update failed: {msg}", None).to_json(), 500
        return ResponseMessage(
            200,
            "parse success",
            {"doc_id": doc_id, "chunk_size": len(chunks), "parse_path": parse_path, "chunk_ids": chunk_ids},
        ).to_json()
    except Exception as e:
        return ResponseMessage(400, f"parse failed: {str(e)}", None).to_json(), 400
