import json
import os
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

    def _mark_chunk_status_from_saved(self, doc_id: str, parse_path: str) -> None:
        print("[DEBUG] enter KnowledgeService._mark_chunk_status_from_saved | core:", {"doc_id": doc_id, "parse_path": (parse_path[:100] + "...") if isinstance(parse_path, str) and len(parse_path) > 100 else parse_path})
        if not os.path.exists(parse_path):
            self.file_service.update_chunk_status(doc_id=doc_id, is_chunked=0, chunk_ids="", chunk_size=0)
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

    def _run_async_parse(self, doc_id: str, file_path: str, classification: str, ext_hint: str = "") -> None:
        print("[DEBUG] enter KnowledgeService._run_async_parse | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        parse_path = os.path.join(PARSED_DIR, f"{doc_id}.json")
        try:
            self._set_parse_progress(doc_id=doc_id, status="running", progress=0.01, message="task started")
            self.rag.index_file(
                file_path=file_path,
                doc_id=doc_id,
                classification=classification,
                force=True,
                file_type=ext_hint,
                parsed_output_path=parse_path,
                progress_callback=lambda p, m: self._set_parse_progress(doc_id=doc_id, status="running", progress=p, message=m),
            )
            KnowledgeService._indexed_docs.add(doc_id)
            self._mark_chunk_status_from_saved(doc_id=doc_id, parse_path=parse_path)
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
        except Exception:
            self.file_service.update_chunk_status(doc_id=doc_id, is_chunked=0, chunk_ids="", chunk_size=0)
            self._set_parse_progress(doc_id=doc_id, status="failed", progress=1.0, message="parse failed")
        finally:
            with KnowledgeService._parse_lock:
                KnowledgeService._parse_jobs.pop(doc_id, None)

    def _submit_async_parse(self, doc_id: str, file_path: str, classification: str, ext_hint: str = "") -> None:
        print("[DEBUG] enter KnowledgeService._submit_async_parse | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        with KnowledgeService._parse_lock:
            old = KnowledgeService._parse_jobs.get(doc_id)
            if old and not old.done():
                return
            self._set_parse_progress(doc_id=doc_id, status="pending", progress=0.0, message="queued")
            fut = KnowledgeService._parse_pool.submit(
                self._run_async_parse,
                doc_id,
                file_path,
                classification,
                ext_hint,
            )
            KnowledgeService._parse_jobs[doc_id] = fut

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
            item = {
                "doc_id": doc_id,
                "status": status,
                "progress": max(0.0, min(1.0, float(progress))),
                "message": message,
                "chunk_size": current.get("chunk_size", 0),
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            if chunk_size is not None:
                item["chunk_size"] = int(chunk_size)
            KnowledgeService._parse_progress[doc_id] = item

    def get_parse_progress(self, doc_id: str = "") -> Dict[str, Any]:
        with KnowledgeService._parse_lock:
            self._cleanup_parse_progress_locked()
            if doc_id:
                return {"tasks": [KnowledgeService._parse_progress.get(doc_id, {"doc_id": doc_id, "status": "unknown", "progress": 0.0, "message": ""})]}
            tasks = list(KnowledgeService._parse_progress.values())
            return {"tasks": tasks}

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

    def upload_knowledge(self, file_obj, classification: str, affect_range: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        print("[DEBUG] enter KnowledgeService.upload_knowledge | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        ok, msg, data = self.file_service.upload_file(file_obj, classification=classification, affect_range=affect_range)
        if ok and data:
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
                )
                latest = self.file_service.get_file_by_doc_id(data["doc_id"])
                if latest:
                    data = latest
                msg = "file uploaded, async parsing started"
                data = dict(data or {})
                data["parse_status"] = "pending"
                data["parse_progress"] = 0.0
            except Exception:
                msg = "file uploaded, async parsing submission failed"
        return ok, msg, data

    def update_knowledge(self, doc_id: str, payload: Dict[str, Any]) -> Tuple[bool, str]:
        print("[DEBUG] enter KnowledgeService.update_knowledge | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        return self.file_service.update_file(doc_id, payload)

    def delete_knowledge(self, doc_id: str) -> Tuple[bool, str]:
        print("[DEBUG] enter KnowledgeService.delete_knowledge | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        ok, msg = self.file_service.delete_file(doc_id)
        if ok:
            self.rag.store.delete_by_doc(doc_id)
            KnowledgeService._indexed_docs.discard(doc_id)
        return ok, msg

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
                    parse_path = os.path.join(PARSED_DIR, f"{r.doc_id}.json")
                    # Semantic query must not trigger parsing; only rebuild from existing parsed results.
                    if not os.path.exists(parse_path):
                        continue
                    with open(parse_path, "r", encoding="utf-8") as f:
                        parsed_rows = json.load(f)
                    if not isinstance(parsed_rows, list) or not parsed_rows:
                        continue
                    self.rag.index_preparsed(
                        doc_id=r.doc_id,
                        parsed_rows=parsed_rows,
                        classification=r.classification or "",
                        force=False,
                    )
                    KnowledgeService._indexed_docs.add(r.doc_id)
                except Exception:
                    continue
        finally:
            session.close()

    def semantic_query(
        self,
        query: str,
        top_k: int = 10,
        classification: str = "",
        min_score: float = 0.6,
    ) -> Dict[str, Any]:
        print("[DEBUG] enter KnowledgeService.semantic_query | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        # Do NOT trigger parsing during semantic search. Parsing is async on upload.
        # Only rebuild vector index from existing parsed artifacts if needed.
        self._ensure_index_for_query(classification=classification)
        filters = {"classification": classification} if classification else None
        ctx = self.rag.build_context(query=query, top_k=top_k, min_score=min_score, filters=filters)
        hits = [
            {
                "doc_id": h["doc_id"],
                "chunk_id": h["chunk_id"],
                "item_type": h.get("item_type", "chunk"),
                "chunk_order": h.get("chunk_order"),
                "section_id": h.get("section_id"),
                "section_code": h.get("section_code"),
                "section_name": h.get("section_name"),
                "unit_type": h.get("unit_type"),
                "page": h["page"],
                "classification": h["classification"],
                "summary": h.get("summary", ""),
                "keywords": h.get("keywords", []),
                "doc_summary": h.get("doc_summary", ""),
                "doc_keywords": h.get("doc_keywords", []),
                "related_chunks": h.get("related_chunks", []),
                "score": h["score"],
                "vector_score": h["vector_score"],
                "lexical_score": h["lexical_score"],
                "content": h["text"],
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
                    "score": h.get("score"),
                    "summary": h.get("summary", ""),
                }
            )
            if not grouped_docs[doc_id]["related_chunks"] and h.get("related_chunks"):
                grouped_docs[doc_id]["related_chunks"] = h.get("related_chunks", [])
        return {"list": hits, "hits": hits, "grouped_docs": list(grouped_docs.values())}

    def submit_parse(self, doc_id: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
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
        )
        return True, "parse task submitted", {"doc_id": doc_id, "status": "pending", "progress": 0.0}
