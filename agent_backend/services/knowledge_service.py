import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from threading import RLock
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_

from agent.agent_backend.config.settings import settings
from agent.agent_backend.database.mysql.db_model import FileInfo
from agent.agent_backend.database.mysql.mysql_conn import MysqlConnection
from agent.agent_backend.memory.rag.pipeline import RAGPipeline
from agent.agent_backend.services.file_service import FileService
from agent.agent_backend.utils.file_util import ensure_dir_exists
from agent.agent_backend.utils.parser import ParserManager


PARSED_DIR = settings.parse_dir
ensure_dir_exists(PARSED_DIR)


class KnowledgeService:
    _rag_pipeline: RAGPipeline | None = None
    _indexed_docs: set[str] = set()
    _parse_pool: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=max(2, int(os.getenv("KB_PARSE_WORKERS", "2"))))
    _parse_jobs: Dict[str, Any] = {}
    _parse_lock: RLock = RLock()
    _parse_progress: Dict[str, Dict[str, Any]] = {}
    _max_progress_entries: int = int(os.getenv("KB_PROGRESS_MAX_ENTRIES", "2000"))
    _progress_ttl_seconds: int = int(os.getenv("KB_PROGRESS_TTL_SECONDS", "7200"))
    _debug_last_output: Dict[str, str] = {}

    def __init__(self):
        print("[DEBUG] enter KnowledgeService.__init__ | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        self.file_service = FileService()
        self.db_conn = MysqlConnection()
        if KnowledgeService._rag_pipeline is None:
            KnowledgeService._rag_pipeline = RAGPipeline()

    @property
    def rag(self) -> RAGPipeline:
        print("[DEBUG] enter KnowledgeService.rag | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        return KnowledgeService._rag_pipeline

    def _parse_and_mark_chunks(self, doc_id: str, file_path: str, file_type: str = "") -> None:
        print("[DEBUG] enter KnowledgeService._parse_and_mark_chunks | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        ext_hint = (file_type or "").strip().lower()
        if not ext_hint and "." in os.path.basename(file_path):
            ext_hint = os.path.basename(file_path).rsplit(".", 1)[-1].lower()
        print(f"[RAGDebug] _parse_and_mark_chunks.input: doc_id={doc_id}, file_path={file_path}, ext_hint={ext_hint}")
        chunks = ParserManager.parse(file_path, ext_hint=ext_hint)
        parse_path = os.path.join(PARSED_DIR, f"{doc_id}.json")
        with open(parse_path, "w", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)
        chunk_ids = [str(item.get("chunk_id", idx + 1)) for idx, item in enumerate(chunks)]
        self.file_service.update_chunk_status(
            doc_id=doc_id,
            is_chunked=1,
            chunk_ids=";".join(chunk_ids),
            chunk_size=len(chunks),
        )
        print(f"[RAGDebug] _parse_and_mark_chunks.output: parse_path={parse_path}, chunk_count={len(chunks)}, chunk_ids={chunk_ids[:20]}")

    def _mark_chunk_status_from_saved(self, doc_id: str, parse_path: str) -> None:
        print("[DEBUG] enter KnowledgeService._mark_chunk_status_from_saved | core:", {"doc_id": doc_id, "parse_path": (parse_path[:100] + "...") if isinstance(parse_path, str) and len(parse_path) > 100 else parse_path})
        if not os.path.exists(parse_path):
            self.file_service.update_chunk_status(doc_id=doc_id, is_chunked=0, chunk_ids="", chunk_size=0)
            print(f"[RAGDebug] _mark_chunk_status_from_saved.output: doc_id={doc_id}, parse_path_missing=True")
            return
        with open(parse_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)
        if not isinstance(chunks, list):
            chunks = []
        chunk_ids = [str(item.get("chunk_id", idx + 1)) for idx, item in enumerate(chunks) if isinstance(item, dict)]
        self.file_service.update_chunk_status(
            doc_id=doc_id,
            is_chunked=1 if chunks else 0,
            chunk_ids=";".join(chunk_ids),
            chunk_size=len(chunks),
        )
        print(f"[RAGDebug] _mark_chunk_status_from_saved.output: doc_id={doc_id}, chunk_count={len(chunks)}, chunk_ids={chunk_ids[:20]}")

    def _run_async_parse(self, doc_id: str, file_path: str, classification: str, ext_hint: str = "", force: bool = True) -> None:
        print("[DEBUG] enter KnowledgeService._run_async_parse | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        parse_path = os.path.join(PARSED_DIR, f"{doc_id}.json")
        print(f"[RAGDebug] _run_async_parse.input: doc_id={doc_id}, file_path={file_path}, classification={classification}, ext_hint={ext_hint}, parse_path={parse_path}")
        try:
            self._set_parse_progress(doc_id=doc_id, status="running", progress=0.01, message="task started")
            self.file_service.update_index_status(
                doc_id=doc_id,
                index_status="running",
                index_error="",
                indexed_at=None,
                vector_count=0,
            )
            self.rag.index_file(
                file_path=file_path,
                doc_id=doc_id,
                classification=classification,
                force=bool(force),
                file_type=ext_hint,
                parsed_output_path=parse_path,
                progress_callback=lambda p, m: self._set_parse_progress(doc_id=doc_id, status="running", progress=p, message=m),
            )
            KnowledgeService._indexed_docs.add(doc_id)
            self._mark_chunk_status_from_saved(doc_id=doc_id, parse_path=parse_path)
            has_doc = False
            vector_count = 0
            try:
                has_doc = bool(self.rag.store.has_doc(doc_id))
                vector_count = len(self.rag.store.list_by_doc(doc_id))
            except Exception:
                has_doc = False
                vector_count = 0
            if (not has_doc) or vector_count <= 0:
                raise RuntimeError(
                    f"index verification failed: doc_id={doc_id}, has_doc={has_doc}, vector_count={vector_count}"
                )
            chunk_size = 0
            if os.path.exists(parse_path):
                try:
                    with open(parse_path, "r", encoding="utf-8") as f:
                        saved = json.load(f)
                    chunk_size = len(saved) if isinstance(saved, list) else 0
                except Exception:
                    chunk_size = 0
            self._set_parse_progress(
                doc_id=doc_id,
                status="completed",
                progress=1.0,
                message="parse completed",
                chunk_size=chunk_size,
            )
            self.file_service.update_index_status(
                doc_id=doc_id,
                index_status="completed",
                index_error="",
                indexed_at=datetime.now(),
                vector_count=vector_count,
            )
            print(
                f"[RAGDebug] _run_async_parse.verify: doc_id={doc_id}, "
                f"has_doc={has_doc}, vector_count={vector_count}, parse_path={parse_path}"
            )
            print(
                f"[RAGDebug] _run_async_parse.output: doc_id={doc_id}, "
                f"status=completed, chunk_size={chunk_size}, vector_count={vector_count}, parse_path={parse_path}"
            )
        except Exception as exc:
            self.file_service.update_chunk_status(doc_id=doc_id, is_chunked=0, chunk_ids="", chunk_size=0)
            self._set_parse_progress(doc_id=doc_id, status="failed", progress=1.0, message="parse failed")
            self.file_service.update_index_status(
                doc_id=doc_id,
                index_status="failed",
                index_error=str(exc),
                indexed_at=None,
                vector_count=0,
            )
            print(f"[RAGDebug] _run_async_parse.output: doc_id={doc_id}, status=failed, error={exc}")
        finally:
            with KnowledgeService._parse_lock:
                KnowledgeService._parse_jobs.pop(doc_id, None)

    def _submit_async_parse(self, doc_id: str, file_path: str, classification: str, ext_hint: str = "", force: bool = True) -> None:
        print("[DEBUG] enter KnowledgeService._submit_async_parse | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        with KnowledgeService._parse_lock:
            old = KnowledgeService._parse_jobs.get(doc_id)
            if old and not old.done():
                print(f"[RAGDebug] _submit_async_parse.skip: doc_id={doc_id}, reason=job_running")
                return
            self._set_parse_progress(doc_id=doc_id, status="pending", progress=0.0, message="queued")
            fut = KnowledgeService._parse_pool.submit(
                self._run_async_parse,
                doc_id,
                file_path,
                classification,
                ext_hint,
                force,
            )
            KnowledgeService._parse_jobs[doc_id] = fut
            print(f"[RAGDebug] _submit_async_parse.output: doc_id={doc_id}, status=pending, future_created=True")

    def _set_parse_progress(
        self,
        doc_id: str,
        status: str,
        progress: float,
        message: str = "",
        chunk_size: int | None = None,
    ) -> None:
        with KnowledgeService._parse_lock:
            self._cleanup_parse_progress_locked()
            current = KnowledgeService._parse_progress.get(doc_id, {})
            inferred_chunk_size = chunk_size
            if inferred_chunk_size is None:
                msg = str(message or "")
                match = re.search(r"chunks=(\d+)", msg)
                if not match:
                    match = re.search(r"enrich chunk \d+/(\d+)", msg)
                if match:
                    inferred_chunk_size = int(match.group(1))
            item = {
                "doc_id": doc_id,
                "status": status,
                "progress": max(0.0, min(1.0, float(progress))),
                "message": message,
                "chunk_size": current.get("chunk_size", 0),
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            if inferred_chunk_size is not None:
                item["chunk_size"] = int(inferred_chunk_size)
            KnowledgeService._parse_progress[doc_id] = item
            self._debug_print_unique(f"_set_parse_progress:{doc_id}", item)

    @classmethod
    def _debug_print_unique(cls, label: str, payload: Any) -> None:
        try:
            rendered = json.dumps(payload, ensure_ascii=False, indent=2)
        except Exception:
            rendered = str(payload)
        if cls._debug_last_output.get(label) == rendered:
            return
        cls._debug_last_output[label] = rendered
        print(f"[RAGDebug] {label}.output:")
        print(rendered)

    def get_parse_progress(self, doc_id: str = "") -> Dict[str, Any]:
        with KnowledgeService._parse_lock:
            self._cleanup_parse_progress_locked()
            if doc_id:
                result = {"tasks": [KnowledgeService._parse_progress.get(doc_id, {"doc_id": doc_id, "status": "unknown", "progress": 0.0, "message": ""})]}
                self._debug_print_unique(f"get_parse_progress:{doc_id or 'all'}", result)
                return result
            tasks = list(KnowledgeService._parse_progress.values())
            result = {"tasks": tasks}
            self._debug_print_unique("get_parse_progress:all", result)
            return result

    def _cleanup_parse_progress_locked(self) -> None:
        if not KnowledgeService._parse_progress:
            return
        now = datetime.now()
        keep: Dict[str, Dict[str, Any]] = {}
        for k, v in KnowledgeService._parse_progress.items():
            ts = str(v.get("updated_at", "") or "")
            expired = False
            try:
                dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                expired = (now - dt).total_seconds() > KnowledgeService._progress_ttl_seconds
            except Exception:
                expired = False
            if not expired:
                keep[k] = v

        # Bound memory size by keeping newest N updates.
        if len(keep) > KnowledgeService._max_progress_entries:
            items = sorted(
                keep.items(),
                key=lambda x: str((x[1] or {}).get("updated_at", "")),
                reverse=True,
            )
            keep = dict(items[: KnowledgeService._max_progress_entries])
        KnowledgeService._parse_progress = keep

    def upload_knowledge(
        self,
        file_obj,
        classification: str,
        affect_range: str,
        profession_classification: str = "other",
        registration_scope: str = "other",
        registration_path: str = "",
        experience_type: str = "other",
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        print("[DEBUG] enter KnowledgeService.upload_knowledge | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        print(
            f"[RAGDebug] upload_knowledge.input: file_name={getattr(file_obj, 'filename', '')}, "
            f"classification={classification}, affect_range={affect_range}, "
            f"profession_classification={profession_classification}, "
            f"registration_scope={registration_scope}, registration_path={registration_path}, "
            f"experience_type={experience_type}"
        )
        ok, msg, data = self.file_service.upload_file(
            file_obj,
            classification=classification,
            affect_range=affect_range,
            profession_classification=profession_classification,
            registration_scope=registration_scope,
            registration_path=registration_path,
            experience_type=experience_type,
        )
        if ok and data:
            ok, msg, data = self._finalize_uploaded_knowledge(data, classification)
        print("[RAGDebug] upload_knowledge.output:")
        print(json.dumps({"ok": ok, "msg": msg, "data": data}, ensure_ascii=False, indent=2))
        return ok, msg, data

    def upload_local_knowledge(
        self,
        file_path: str,
        file_name: str,
        classification: str,
        affect_range: str,
        profession_classification: str = "other",
        registration_scope: str = "other",
        registration_path: str = "",
        experience_type: str = "other",
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        print(
            f"[RAGDebug] upload_local_knowledge.input: file_path={file_path}, file_name={file_name}, "
            f"classification={classification}, affect_range={affect_range}, "
            f"profession_classification={profession_classification}, registration_scope={registration_scope}, "
            f"registration_path={registration_path}, experience_type={experience_type}"
        )
        ok, msg, data = self.file_service.add_file(
            file_path=file_path,
            file_name=file_name,
            classification=classification,
            affect_range=affect_range,
            profession_classification=profession_classification,
            registration_scope=registration_scope,
            registration_path=registration_path,
            experience_type=experience_type,
        )
        if ok and data:
            ok, msg, data = self._finalize_uploaded_knowledge(data, classification)
        print("[RAGDebug] upload_local_knowledge.output:")
        print(json.dumps({"ok": ok, "msg": msg, "data": data}, ensure_ascii=False, indent=2))
        return ok, msg, data

    def _finalize_uploaded_knowledge(
        self,
        data: Dict[str, Any],
        classification: str,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        try:
            ext_hint = str(data.get("file_type", "") or "").strip()
            if not ext_hint:
                file_name = str(data.get("file_name", "") or "")
                if "." in file_name:
                    ext_hint = file_name.rsplit(".", 1)[-1].lower()
            self._submit_async_parse(
                doc_id=data["doc_id"],
                file_path=data["file_path"],
                classification=classification,
                ext_hint=ext_hint,
                force=True,
            )
            self.file_service.update_index_status(
                doc_id=data["doc_id"],
                index_status="pending",
                index_error="",
                indexed_at=None,
                vector_count=0,
            )
            latest = self.file_service.get_file_by_doc_id(data["doc_id"])
            if latest:
                data = latest
            result = dict(data or {})
            result["parse_status"] = "pending"
            result["parse_progress"] = 0.0
            return True, "file uploaded, async parsing started", result
        except Exception:
            result = dict(data or {})
            return True, "file uploaded, async parsing submission failed", result

    def update_knowledge(self, doc_id: str, payload: Dict[str, Any]) -> Tuple[bool, str]:
        print("[DEBUG] enter KnowledgeService.update_knowledge | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        return self.file_service.update_file(doc_id, payload)

    def delete_knowledge(self, doc_id: str) -> Tuple[bool, str]:
        print("[DEBUG] enter KnowledgeService.delete_knowledge | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        ok, msg = self.file_service.delete_file(doc_id)
        if ok:
            KnowledgeService._indexed_docs.discard(doc_id)
        return ok, msg

    def delete_knowledge_batch(self, doc_ids: List[Any]) -> Tuple[bool, str, Dict[str, Any]]:
        normalized = []
        seen = set()
        for item in doc_ids or []:
            doc_id = str(item or "").strip()
            if not doc_id or doc_id in seen:
                continue
            seen.add(doc_id)
            normalized.append(doc_id)
        if not normalized:
            return False, "doc_ids is required", {
                "requested_count": 0,
                "deleted_count": 0,
                "failed_count": 0,
                "deleted_doc_ids": [],
                "failed": [],
            }

        deleted_doc_ids: List[str] = []
        failed: List[Dict[str, str]] = []
        for doc_id in normalized:
            ok, msg = self.delete_knowledge(doc_id)
            if ok:
                deleted_doc_ids.append(doc_id)
            else:
                failed.append({"doc_id": doc_id, "message": msg})

        data = {
            "requested_count": len(normalized),
            "deleted_count": len(deleted_doc_ids),
            "failed_count": len(failed),
            "deleted_doc_ids": deleted_doc_ids,
            "failed": failed,
        }
        if not deleted_doc_ids:
            return False, "batch delete failed", data
        if failed:
            return True, f"batch delete completed with {len(failed)} failures", data
        return True, "batch delete completed", data

    def _keyword_match_in_parsed(self, doc_id: str, keyword: str) -> bool:
        print("[DEBUG] enter KnowledgeService._keyword_match_in_parsed | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        parsed_path = os.path.join(PARSED_DIR, f"{doc_id}.json")
        if not os.path.exists(parsed_path):
            return False
        try:
            with open(parsed_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            text = json.dumps(data, ensure_ascii=False)
            return keyword.lower() in text.lower()
        except Exception:
            return False

    def query_knowledge(
        self,
        file_name: str = "",
        keyword: str = "",
        file_type: str = "",
        classification: str = "",
        affect_range: str = "",
        profession_classification: str = "",
        registration_scope: str = "",
        registration_path: str = "",
        experience_type: str = "",
        start_time: str = "",
        end_time: str = "",
        page: int = 1,
        page_size: int = 10,
    ) -> Dict[str, Any]:
        print("[DEBUG] enter KnowledgeService.query_knowledge | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        session = self.db_conn.get_session()
        try:
            conditions = [FileInfo.is_deleted == 0]
            if file_name:
                conditions.append(FileInfo.file_name.like(f"%{file_name}%"))
            if file_type:
                conditions.append(FileInfo.file_type == file_type)
            if classification:
                conditions.append(FileInfo.classification == classification)
            if affect_range:
                conditions.append(FileInfo.affect_range == affect_range)
            if profession_classification:
                conditions.append(FileInfo.profession_classification == profession_classification)
            if registration_scope:
                conditions.append(FileInfo.registration_scope == registration_scope)
            if experience_type:
                conditions.append(FileInfo.experience_type == experience_type)
            if start_time:
                conditions.append(FileInfo.create_time >= start_time)
            if end_time:
                conditions.append(FileInfo.create_time <= end_time)

            query = session.query(FileInfo).filter(and_(*conditions))
            rows = query.order_by(FileInfo.id.desc()).all()

            if keyword:
                rows = [
                    r
                    for r in rows
                    if keyword.lower() in (r.file_name or "").lower()
                    or self._keyword_match_in_parsed(r.doc_id, keyword)
                ]
            if registration_path:
                rows = [
                    r for r in rows
                    if registration_path.lower() in str(getattr(r, "registration_path", "") or "").lower()
                ]

            total = len(rows)
            page = max(1, int(page))
            page_size = max(1, int(page_size))
            start = (page - 1) * page_size
            end = start + page_size
            sub = rows[start:end]

            data = []
            for r in sub:
                data.append(
                    {
                        "doc_id": r.doc_id,
                        "file_name": r.file_name,
                        "file_type": r.file_type,
                        "classification": r.classification,
                        "affect_range": r.affect_range,
                        "profession_classification": getattr(r, "profession_classification", "other") or "other",
                        "registration_scope": getattr(r, "registration_scope", "other") or "other",
                        "registration_path": getattr(r, "registration_path", "") or "",
                        "experience_type": getattr(r, "experience_type", "other") or "other",
                        "create_time": r.create_time,
                        "is_chunked": bool(r.is_chunked),
                        "review_status": r.review_status,
                        "parse_status": "unknown",
                        "parse_progress": 0.0,
                        "parse_message": "",
                    }
                )

            progress_map = self.get_parse_progress().get("tasks", [])
            progress_by_doc = {x.get("doc_id"): x for x in progress_map if isinstance(x, dict)}
            for item in data:
                p = progress_by_doc.get(item.get("doc_id"))
                if not p:
                    item["parse_status"] = "completed" if item.get("is_chunked") else "unknown"
                    item["parse_progress"] = 1.0 if item.get("is_chunked") else 0.0
                    continue
                item["parse_status"] = p.get("status", "unknown")
                item["parse_progress"] = float(p.get("progress", 0.0))
                item["parse_message"] = p.get("message", "")

            return {
                "list": data,
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size,
            }
        finally:
            session.close()

    def _ensure_index_for_query(self, classification: str = "") -> None:
        print("[DEBUG] enter KnowledgeService._ensure_index_for_query | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        session = self.db_conn.get_session()
        try:
            q = session.query(FileInfo).filter(FileInfo.is_deleted == 0)
            if classification:
                q = q.filter(FileInfo.classification == classification)
            rows = q.all()
            for r in rows:
                if r.doc_id in KnowledgeService._indexed_docs:
                    continue
                try:
                    if self.rag.store.has_doc(r.doc_id):
                        KnowledgeService._indexed_docs.add(r.doc_id)
                        continue
                except Exception:
                    pass
                continue
        finally:
            session.close()

    def semantic_query(
        self,
        query: str,
        top_k: int = 10,
        classification: str = "",
        min_score: float = 0.0,
    ) -> Dict[str, Any]:
        print("[DEBUG] enter KnowledgeService.semantic_query | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        print(f"[RAGDebug] semantic_query.input: query={query!r}, top_k={top_k}, classification={classification!r}, min_score={min_score}")
        # Do NOT trigger parsing during semantic search. Parsing is async on upload.
        # Only rebuild vector index from existing parsed artifacts if needed.
        self._ensure_index_for_query(classification=classification)
        filters = {"classification": classification} if classification else None
        ctx = self.rag.build_context(query=query, top_k=top_k, min_score=min_score, filters=filters)
        hits = [
            {
                "doc_id": h.get("doc_id", ""),
                "chunk_id": h.get("chunk_id", ""),
                "item_type": h.get("item_type", "chunk"),
                "chunk_order": h.get("chunk_order"),
                "section_id": h.get("section_id"),
                "section_code": h.get("section_code"),
                "section_name": h.get("section_name"),
                "unit_type": h.get("unit_type"),
                "page": h.get("page"),
                "page_start": h.get("page_start"),
                "page_end": h.get("page_end"),
                "classification": h.get("classification", ""),
                "summary": h.get("summary", ""),
                "keywords": h.get("keywords", []),
                "doc_summary": h.get("doc_summary", ""),
                "doc_keywords": h.get("doc_keywords", []),
                "related_chunks": h.get("related_chunks", []),
                "score": h.get("final_score", h.get("score", 0.0)),
                "vector_score": h.get("vector_score", 0.0),
                "lexical_score": h.get("lexical_score", 0.0),
                "content": h.get("text", ""),
            }
            for h in ctx["hits"]
        ]
        grouped_docs: Dict[str, Dict[str, Any]] = {}
        for h in hits:
            doc_id = str(h.get("doc_id", ""))
            if not doc_id:
                continue
            if doc_id not in grouped_docs:
                grouped_docs[doc_id] = {
                    "doc_id": doc_id,
                    "doc_summary": h.get("doc_summary", ""),
                    "doc_keywords": h.get("doc_keywords", []),
                    "matched_hits": [],
                    "related_chunks": h.get("related_chunks", []),
                }
            grouped_docs[doc_id]["matched_hits"].append(
                {
                    "chunk_id": h.get("chunk_id"),
                    "item_type": h.get("item_type", "chunk"),
                    "score": h.get("final_score", h.get("score", 0.0)),
                    "page": h.get("page"),
                    "page_start": h.get("page_start"),
                    "page_end": h.get("page_end"),
                    "section_name": h.get("section_name"),
                    "summary": h.get("summary", ""),
                    "content": h.get("content", ""),
                }
            )
            if not grouped_docs[doc_id]["related_chunks"] and h.get("related_chunks"):
                grouped_docs[doc_id]["related_chunks"] = h.get("related_chunks", [])
        result = {"list": hits, "hits": hits, "grouped_docs": list(grouped_docs.values())}
        print(f"[RAGDebug] semantic_query.output: hits={len(hits)}, grouped_docs={len(result['grouped_docs'])}")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result

    def submit_parse(self, doc_id: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        print(f"[RAGDebug] submit_parse.input: doc_id={doc_id}")
        file_info = self.file_service.get_file_by_doc_id(doc_id)
        if not file_info:
            print(f"[RAGDebug] submit_parse.output: ok=False, reason=file not found, doc_id={doc_id}")
            return False, "file not found", None

        file_path = str(file_info.get("file_path", "") or "").strip()
        if not file_path or not os.path.exists(file_path):
            print(f"[RAGDebug] submit_parse.output: ok=False, reason=file path not exists, doc_id={doc_id}, file_path={file_path}")
            return False, "file path not exists", None

        ext_hint = str(file_info.get("file_type", "") or "").strip().lower()
        if not ext_hint:
            file_name = str(file_info.get("file_name", "") or "")
            if "." in file_name:
                ext_hint = file_name.rsplit(".", 1)[-1].lower()

        classification = str(file_info.get("classification", "") or "")
        self._submit_async_parse(
            doc_id=doc_id,
            file_path=file_path,
            classification=classification,
            ext_hint=ext_hint,
            force=True,
        )
        result = {"doc_id": doc_id, "status": "pending", "progress": 0.0}
        print("[RAGDebug] submit_parse.output:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return True, "parse task submitted", result

    def submit_reindex(self, doc_id: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        file_info = self.file_service.get_file_by_doc_id(doc_id)
        if not file_info:
            return False, "file not found", None
        file_path = str(file_info.get("file_path", "") or "").strip()
        if not file_path or not os.path.exists(file_path):
            return False, "file path not exists", None
        ext_hint = str(file_info.get("file_type", "") or "").strip().lower()
        if not ext_hint:
            file_name = str(file_info.get("file_name", "") or "")
            if "." in file_name:
                ext_hint = file_name.rsplit(".", 1)[-1].lower()
        classification = str(file_info.get("classification", "") or "")
        self._submit_async_parse(
            doc_id=doc_id,
            file_path=file_path,
            classification=classification,
            ext_hint=ext_hint,
            force=True,
        )
        result = {"doc_id": doc_id, "status": "pending", "progress": 0.0}
        return True, "reindex task submitted", result
