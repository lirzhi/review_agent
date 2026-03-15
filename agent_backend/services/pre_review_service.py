import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from docx import Document
from sqlalchemy import and_, desc, func
from werkzeug.utils import secure_filename

from agent.agent_backend.agents.pre_review_agent.pre_review_agent import build_pre_review_agent
from agent.agent_backend.common_tools.builtin.memory_tool import MemoryTool
from agent.agent_backend.config.settings import settings
from agent.agent_backend.database.mysql.db_model import (
    FileInfo,
    PreReviewFeedback,
    PreReviewProject,
    PreReviewRun,
    PreReviewSectionConclusion,
    PreReviewSubmissionFile,
    PreReviewSectionTrace,
)
from agent.agent_backend.database.mysql.mysql_conn import MysqlConnection
from agent.agent_backend.agentic_rl.reward_functions import feedback_metrics
from agent.agent_backend.services.knowledge_service import KnowledgeService
from agent.agent_backend.utils.file_util import ensure_dir_exists
from agent.agent_backend.utils.parser import ParserManager
from agent.agent_backend.utils.parser.submission_material_parser import parse_submission_material


SUBMISSION_UPLOAD_DIR = settings.submission_upload_dir
SUBMISSION_PARSED_DIR = settings.submission_parse_dir
REPORT_DIR = settings.report_dir
ensure_dir_exists(SUBMISSION_UPLOAD_DIR)
ensure_dir_exists(SUBMISSION_PARSED_DIR)
ensure_dir_exists(REPORT_DIR)


class PreReviewService:
    def __init__(self):
        print("[DEBUG] enter PreReviewService.__init__ | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        self.db_conn = MysqlConnection()
        self.memory_tool = MemoryTool()
        self.agent = build_pre_review_agent(memory_tool=self.memory_tool)
        self.knowledge = KnowledgeService()

    @staticmethod
    def _now() -> datetime:
        print("[DEBUG] enter PreReviewService._now | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        return datetime.now()

    @staticmethod
    def _new_project_id() -> str:
        print("[DEBUG] enter PreReviewService._new_project_id | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        return f"prj_{uuid.uuid4().hex[:12]}"

    @staticmethod
    def _new_run_id() -> str:
        print("[DEBUG] enter PreReviewService._new_run_id | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        return f"run_{uuid.uuid4().hex[:12]}"

    @staticmethod
    def _new_submission_doc_id() -> str:
        print("[DEBUG] enter PreReviewService._new_submission_doc_id | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        return f"sub_{uuid.uuid4().hex[:16]}"

    @staticmethod
    def _safe_display_name(file_name: str) -> str:
        print("[DEBUG] enter PreReviewService._safe_display_name | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        return os.path.basename(str(file_name or "")).strip()

    @staticmethod
    def _submission_storage_name(doc_id: str, display_name: str) -> str:
        print("[DEBUG] enter PreReviewService._submission_storage_name | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        ext = ""
        if "." in display_name:
            ext = display_name.rsplit(".", 1)[-1].lower().strip()
        safe = secure_filename(display_name) or "submission"
        if ext and "." not in safe:
            safe = f"{safe}.{ext}"
        return f"{doc_id}_{safe}"

    @staticmethod
    def _rule_label(rule_item: Dict[str, Any]) -> str:
        """
        Semantic retrieval currently returns doc_id/content/score fields.
        Build a stable human-readable label for linkage display.
        """
        print("[DEBUG] enter PreReviewService._rule_label | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        doc_id = str(rule_item.get("doc_id", "")).strip()
        classification = str(rule_item.get("classification", "")).strip()
        score = rule_item.get("score", None)
        parts = [p for p in [doc_id, classification] if p]
        label = "/".join(parts) if parts else "rule"
        if score is not None:
            try:
                label = f"{label}(score={float(score):.3f})"
            except Exception:
                pass
        return label

    @staticmethod
    def _preview(value: Any, max_len: int = 180) -> str:
        text = str(value or "").replace("\n", " ").strip()
        return text if len(text) <= max_len else f"{text[:max_len]}..."

    @staticmethod
    def _code_sort_key(code: str) -> Tuple:
        parts = str(code or "").split(".")
        key = []
        for p in parts:
            if p.isdigit():
                key.append((0, int(p)))
            else:
                key.append((1, p))
        return tuple(key)

    def _order_review_units(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return sorted(
            chunks or [],
            key=lambda x: (
                int(x.get("unit_order") or 10**9),
                self._code_sort_key(str(x.get("section_code", ""))),
                int(x.get("page_start") or x.get("page") or 10**9),
                str(x.get("section_id") or x.get("chunk_id") or ""),
            ),
        )

    def _build_section_query(self, section_name: str, section_code: str, text: str, title_path: List[Any]) -> str:
        path = " > ".join([str(x).strip() for x in (title_path or []) if str(x).strip()])
        query_parts = [f"章节: {section_code} {section_name}".strip()]
        if path:
            query_parts.append(f"路径: {path}")
        query_parts.append(f"内容: {self._preview(text, 260)}")
        return "\n".join(query_parts)

    def _classify_risk_level(self, findings: List[str], score: float) -> str:
        text = " ".join([str(x) for x in (findings or [])]).lower()
        high_markers = [
            "禁忌", "严重", "致命", "black box", "contraindication", "fatal", "high risk", "critical",
        ]
        medium_markers = [
            "剂量", "不良反应", "监测", "相互作用", "warning", "adverse", "interaction", "monitor",
        ]
        if any(k in text for k in high_markers):
            return "high"
        if score >= 0.65:
            return "high"
        if any(k in text for k in medium_markers):
            return "medium"
        if score >= 0.25:
            return "medium"
        return "low"

    def _build_coordination_payload(
        self,
        project_id: str,
        run_id: str,
        source_doc_id: str,
        section_meta: Dict[str, Any],
        related_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        hits = related_result.get("list", []) if isinstance(related_result, dict) else []
        grouped_docs = related_result.get("grouped_docs", []) if isinstance(related_result, dict) else []
        hit_digest = []
        for h in hits[:5]:
            if not isinstance(h, dict):
                continue
            hit_digest.append(
                {
                    "doc_id": h.get("doc_id", ""),
                    "chunk_id": h.get("chunk_id", ""),
                    "score": h.get("score", 0.0),
                    "classification": h.get("classification", ""),
                    "summary": self._preview(h.get("summary", "")),
                    "content_preview": self._preview(h.get("content", "")),
                }
            )
        grouped_digest = []
        for g in grouped_docs[:3]:
            if not isinstance(g, dict):
                continue
            grouped_digest.append(
                {
                    "doc_id": g.get("doc_id", ""),
                    "doc_summary": self._preview(g.get("doc_summary", "")),
                    "doc_keywords": g.get("doc_keywords", []),
                    "matched_count": len(g.get("matched_hits", []) or []),
                    "related_chunk_count": len(g.get("related_chunks", []) or []),
                }
            )
        return {
            "coordination_version": "v1",
            "project_id": project_id,
            "run_id": run_id,
            "source_doc_id": source_doc_id,
            "section_meta": section_meta,
            "retrieval": {
                "query": section_meta.get("query", ""),
                "hit_count": len(hits),
                "grouped_doc_count": len(grouped_docs),
                "hits": hit_digest,
                "grouped_docs": grouped_digest,
            },
            "memory_strategy": {
                "metadata_filter": {"project_id": project_id},
                "types": ["episodic", "semantic", "working"],
                "top_k": 8,
            },
        }

    def _seed_submission_structure_memory(
        self,
        project_id: str,
        source_doc_id: str,
        review_units: List[Dict[str, Any]],
    ) -> None:
        """
        Inject section skeleton into semantic memory to stabilize cross-section consistency.
        """
        for unit in review_units or []:
            if not isinstance(unit, dict):
                continue
            section_id = str(unit.get("section_id") or unit.get("chunk_id") or "").strip()
            if not section_id:
                continue
            section_code = str(unit.get("section_code", "")).strip()
            section_name = str(unit.get("section_name", "")).strip()
            title_path = unit.get("title_path", [])
            if not isinstance(title_path, list):
                title_path = []
            skeleton = {
                "section_id": section_id,
                "section_code": section_code,
                "section_name": section_name,
                "parent_code": str(unit.get("parent_code", "")).strip(),
                "unit_type": str(unit.get("unit_type", "")).strip(),
                "unit_order": unit.get("unit_order"),
                "title_path": [str(x).strip() for x in title_path if str(x).strip()],
                "page_start": unit.get("page_start"),
                "page_end": unit.get("page_end"),
            }
            self.memory_tool.remember(
                key=f"outline:{source_doc_id}:{section_id}",
                value=json.dumps(skeleton, ensure_ascii=False),
                memory_type="semantic",
                metadata={
                    "source": "submission_outline",
                    "project_id": project_id,
                    "doc_id": source_doc_id,
                    "section_id": section_id,
                },
            )

    def create_project(self, project_name: str, description: str = "", owner: str = "") -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        print("[DEBUG] enter PreReviewService.create_project | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        if not project_name:
            return False, "project_name is required", None
        session = self.db_conn.get_session()
        try:
            entity = PreReviewProject(
                project_id=self._new_project_id(),
                project_name=project_name,
                description=description,
                status="created",
                progress=0.0,
                owner=owner,
                create_time=self._now(),
                update_time=self._now(),
                is_deleted=False,
            )
            session.add(entity)
            session.commit()
            return True, "project created", {"project_id": entity.project_id, "project_name": entity.project_name}
        except Exception as e:
            session.rollback()
            return False, f"create project failed: {str(e)}", None
        finally:
            session.close()

    def delete_project(self, project_id: str) -> Tuple[bool, str]:
        print("[DEBUG] enter PreReviewService.delete_project | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        session = self.db_conn.get_session()
        try:
            row = (
                session.query(PreReviewProject)
                .filter(and_(PreReviewProject.project_id == project_id, PreReviewProject.is_deleted == 0))
                .first()
            )
            if row is None:
                return False, "project not found"
            row.is_deleted = True
            row.status = "archived"
            row.update_time = self._now()
            session.commit()
            return True, "project deleted"
        except Exception as e:
            session.rollback()
            return False, f"delete project failed: {str(e)}"
        finally:
            session.close()

    def list_projects(self, page: int = 1, page_size: int = 10, status: str = "") -> Dict[str, Any]:
        print("[DEBUG] enter PreReviewService.list_projects | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        session = self.db_conn.get_session()
        try:
            query = session.query(PreReviewProject).filter(PreReviewProject.is_deleted == 0)
            if status:
                query = query.filter(PreReviewProject.status == status)
            total = query.count()
            page = max(1, int(page))
            page_size = max(1, int(page_size))
            rows = (
                query.order_by(desc(PreReviewProject.id))
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            return {
                "list": [
                    {
                        "project_id": r.project_id,
                        "project_name": r.project_name,
                        "description": r.description,
                        "status": r.status,
                        "progress": r.progress,
                        "owner": r.owner,
                        "create_time": r.create_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "update_time": r.update_time.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    for r in rows
                ],
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size,
            }
        finally:
            session.close()

    def get_project_detail(self, project_id: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        print("[DEBUG] enter PreReviewService.get_project_detail | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        session = self.db_conn.get_session()
        try:
            row = (
                session.query(PreReviewProject)
                .filter(and_(PreReviewProject.project_id == project_id, PreReviewProject.is_deleted == 0))
                .first()
            )
            if row is None:
                return False, "project not found", None
            return True, "success", {
                "project_id": row.project_id,
                "project_name": row.project_name,
                "description": row.description,
                "status": row.status,
                "progress": row.progress,
                "owner": row.owner,
                "create_time": row.create_time.strftime("%Y-%m-%d %H:%M:%S"),
                "update_time": row.update_time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        finally:
            session.close()

    def upload_submission(self, project_id: str, file_obj) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        print("[DEBUG] enter PreReviewService.upload_submission | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        if file_obj is None or not getattr(file_obj, "filename", ""):
            return False, "file is required", None

        session = self.db_conn.get_session()
        try:
            project = (
                session.query(PreReviewProject)
                .filter(and_(PreReviewProject.project_id == project_id, PreReviewProject.is_deleted == 0))
                .first()
            )
            if project is None:
                return False, "project not found", None

            display_name = self._safe_display_name(file_obj.filename)
            if not display_name:
                return False, "invalid file name", None
            file_type = display_name.rsplit(".", 1)[-1].lower() if "." in display_name else ""
            if not ParserManager.is_supported(file_type):
                return False, f"unsupported file type: {file_type or 'unknown'}", None

            doc_id = self._new_submission_doc_id()
            storage_name = self._submission_storage_name(doc_id, display_name)
            file_path = os.path.join(SUBMISSION_UPLOAD_DIR, storage_name)
            file_obj.save(file_path)

            row = PreReviewSubmissionFile(
                doc_id=doc_id,
                project_id=project_id,
                file_name=display_name,
                file_path=file_path,
                file_type=file_type,
                is_chunked=False,
                chunk_ids="",
                chunk_size=0,
                is_deleted=False,
                create_time=self._now(),
            )
            session.add(row)
            shadow = session.query(FileInfo).filter(FileInfo.doc_id == doc_id).first()
            if shadow is None:
                session.add(
                    FileInfo(
                        doc_id=doc_id,
                        file_name=display_name,
                        file_path=file_path,
                        file_type=file_type,
                        classification="submission_material",
                        affect_range="pre_review",
                        is_chunked=0,
                        chunk_ids="",
                        chunk_size=0,
                        is_deleted=1,
                        create_time=self._now().strftime("%Y-%m-%d %H:%M:%S"),
                        review_status=0,
                        review_time=None,
                    )
                )
            session.commit()
            self._load_doc_chunks(project_id=project_id, doc_id=doc_id)
            return True, "submission uploaded", {
                "doc_id": row.doc_id,
                "project_id": row.project_id,
                "file_name": row.file_name,
                "file_type": row.file_type,
                "is_chunked": bool(row.is_chunked),
                "chunk_size": row.chunk_size or 0,
                "create_time": row.create_time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        except Exception as e:
            session.rollback()
            return False, f"upload submission failed: {str(e)}", None
        finally:
            session.close()

    def list_submissions(self, project_id: str, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        print("[DEBUG] enter PreReviewService.list_submissions | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        session = self.db_conn.get_session()
        try:
            query = session.query(PreReviewSubmissionFile).filter(
                and_(
                    PreReviewSubmissionFile.project_id == project_id,
                    PreReviewSubmissionFile.is_deleted == 0,
                )
            )
            total = query.count()
            page = max(1, int(page))
            page_size = max(1, int(page_size))
            rows = (
                query.order_by(desc(PreReviewSubmissionFile.id))
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            return {
                "list": [
                    {
                        "doc_id": r.doc_id,
                        "project_id": r.project_id,
                        "file_name": r.file_name,
                        "file_type": r.file_type,
                        "is_chunked": bool(r.is_chunked),
                        "chunk_size": r.chunk_size or 0,
                        "create_time": r.create_time.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    for r in rows
                ],
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size,
            }
        finally:
            session.close()

    def get_submission_content(self, project_id: str, doc_id: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        print("[DEBUG] enter PreReviewService.get_submission_content | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        ok, msg, chunks = self._load_doc_chunks(project_id=project_id, doc_id=doc_id)
        if not ok:
            return False, msg, None

        lines = [str(c.get("text", "")).strip() for c in chunks if str(c.get("text", "")).strip()]
        ok_payload, _, payload = self._load_submission_parsed_payload(project_id=project_id, doc_id=doc_id)
        chapter_structure = []
        section_list = []
        leaf_sibling_groups = []
        if ok_payload and isinstance(payload, dict):
            chapter_structure = payload.get("chapter_structure") or []
            section_list = payload.get("sections") or []
            leaf_sibling_groups = payload.get("leaf_sibling_groups") or []
        return True, "success", {
            "doc_id": doc_id,
            "project_id": project_id,
            "content": "\n\n".join(lines),
            "chunk_size": len(chunks),
            "review_unit_count": len(chunks),
            "section_count": len(section_list) if isinstance(section_list, list) else 0,
            "chapter_structure": chapter_structure if isinstance(chapter_structure, list) else [],
            "sections": section_list if isinstance(section_list, list) else [],
            "leaf_sibling_groups": leaf_sibling_groups if isinstance(leaf_sibling_groups, list) else [],
        }

    def get_submission_sections(self, project_id: str, doc_id: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        print("[DEBUG] enter PreReviewService.get_submission_sections | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        ok, msg, payload = self._load_submission_parsed_payload(project_id=project_id, doc_id=doc_id)
        if not ok:
            return False, msg, None
        if isinstance(payload, list):
            # Backward compatibility with old list-only parsed format
            return True, "success", {
                "doc_id": doc_id,
                "project_id": project_id,
                "sections": [],
                "chapter_structure": [],
                "leaf_sibling_groups": [],
                "review_units": payload,
            }
        if not isinstance(payload, dict):
            return True, "success", {
                "doc_id": doc_id,
                "project_id": project_id,
                "sections": [],
                "chapter_structure": [],
                "leaf_sibling_groups": [],
                "review_units": [],
            }
        return True, "success", {
            "doc_id": doc_id,
            "project_id": project_id,
            "sections": payload.get("sections", []),
            "chapter_structure": payload.get("chapter_structure", []),
            "leaf_sibling_groups": payload.get("leaf_sibling_groups", []),
            "review_units": payload.get("review_units", []),
            "statistics": payload.get("statistics", {}),
        }

    def get_submission_file_info(self, project_id: str, doc_id: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        print("[DEBUG] enter PreReviewService.get_submission_file_info | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        session = self.db_conn.get_session()
        try:
            row = (
                session.query(PreReviewSubmissionFile)
                .filter(
                    and_(
                        PreReviewSubmissionFile.project_id == project_id,
                        PreReviewSubmissionFile.doc_id == doc_id,
                        PreReviewSubmissionFile.is_deleted == 0,
                    )
                )
                .first()
            )
            if row is None:
                return False, "submission file not found", None
            if not os.path.exists(row.file_path):
                return False, "submission file path not exists", None
            return True, "success", {
                "doc_id": row.doc_id,
                "project_id": row.project_id,
                "file_name": row.file_name,
                "file_type": row.file_type,
                "file_path": row.file_path,
            }
        finally:
            session.close()

    def _load_doc_chunks(self, project_id: str, doc_id: str) -> Tuple[bool, str, List[Dict[str, Any]]]:
        print("[DEBUG] enter PreReviewService._load_doc_chunks | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        ok, msg, payload = self._load_submission_parsed_payload(project_id=project_id, doc_id=doc_id)
        if not ok:
            return False, msg, []
        if isinstance(payload, dict):
            units = payload.get("review_units")
            if isinstance(units, list):
                return True, "ok", units
            sections = payload.get("sections")
            if isinstance(sections, list):
                fallback = []
                for idx, s in enumerate(sections, start=1):
                    if not isinstance(s, dict):
                        continue
                    text = str(s.get("content", "")).strip()
                    if not text:
                        continue
                    fallback.append(
                        {
                            "chunk_id": str(s.get("section_id", f"sec_{idx}")),
                            "section_id": str(s.get("section_id", f"sec_{idx}")),
                            "section_code": str(s.get("code", "")),
                            "section_name": str(s.get("title", "")),
                            "page": s.get("page_start"),
                            "page_start": s.get("page_start"),
                            "page_end": s.get("page_end"),
                            "text": text,
                        }
                    )
                return True, "ok", fallback
        if isinstance(payload, list):
            return True, "ok", payload
        return True, "ok", []

    def _load_submission_parsed_payload(self, project_id: str, doc_id: str) -> Tuple[bool, str, Any]:
        print("[DEBUG] enter PreReviewService._load_submission_parsed_payload | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        parsed_path = os.path.join(SUBMISSION_PARSED_DIR, f"{doc_id}.json")
        if os.path.exists(parsed_path):
            try:
                with open(parsed_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                if isinstance(payload, (list, dict)):
                    return True, "ok", payload
            except Exception:
                pass

        session = self.db_conn.get_session()
        try:
            file_row = (
                session.query(PreReviewSubmissionFile)
                .filter(
                    and_(
                        PreReviewSubmissionFile.doc_id == doc_id,
                        PreReviewSubmissionFile.project_id == project_id,
                        PreReviewSubmissionFile.is_deleted == 0,
                    )
                )
                .first()
            )
            if file_row is None:
                return False, "source doc not found", []
            ext_hint = (file_row.file_type or "").strip()
            if not ext_hint and file_row.file_name and "." in file_row.file_name:
                ext_hint = file_row.file_name.rsplit(".", 1)[-1].lower()

            payload: Any
            if ext_hint.lower() == "pdf":
                payload = parse_submission_material(file_path=file_row.file_path)
                if not isinstance(payload, dict):
                    payload = {"review_units": []}
            else:
                chunks = self._parse_submission_file(file_path=file_row.file_path, ext_hint=ext_hint)
                payload = {"review_units": chunks}

            with open(parsed_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)

            units = payload.get("review_units", []) if isinstance(payload, dict) else []
            if not isinstance(units, list):
                units = []
            chunk_ids = [str(c.get("chunk_id", idx + 1)) for idx, c in enumerate(units) if isinstance(c, dict)]
            file_row.is_chunked = True
            file_row.chunk_ids = ";".join(chunk_ids)
            file_row.chunk_size = len(units)
            session.commit()
            return True, "ok", payload
        except Exception as e:
            session.rollback()
            return False, f"load doc chunks failed: {str(e)}", {}
        finally:
            session.close()

    def _parse_submission_file(self, file_path: str, ext_hint: str = "") -> List[Dict[str, Any]]:
        """
        Submission parsing pipeline for pre-review only.
        Keep it isolated from knowledge-base semantic indexing pipeline.
        """
        print("[DEBUG] enter PreReviewService._parse_submission_file | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        ext = (ext_hint or "").strip().lower()
        if not ext and "." in os.path.basename(file_path):
            ext = os.path.basename(file_path).rsplit(".", 1)[-1].lower()
        # For PDF submissions, use CTD-oriented structured parser.
        if ext == "pdf":
            parsed = parse_submission_material(file_path=file_path)
            return parsed.get("review_units", []) if isinstance(parsed, dict) else []

        raw_chunks = ParserManager.parse(file_path, ext_hint=ext_hint)
        out: List[Dict[str, Any]] = []
        for idx, item in enumerate(raw_chunks, start=1):
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            out.append(
                {
                    "chunk_id": str(item.get("chunk_id", f"sub_{idx}")),
                    "section_id": str(item.get("chunk_id", f"sub_{idx}")),
                    "section_code": str(item.get("chunk_id", f"sub_{idx}")),
                    "section_name": str(item.get("section_name") or item.get("title") or f"section-{idx}"),
                    "page": item.get("page"),
                    "text": text,
                    "pipeline": "submission_pre_review",
                }
            )
        return out

    def _next_version(self, session, project_id: str) -> int:
        print("[DEBUG] enter PreReviewService._next_version | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        max_ver = session.query(func.max(PreReviewRun.version_no)).filter(PreReviewRun.project_id == project_id).scalar()
        return int(max_ver or 0) + 1

    def _mark_project_failed(self, project_id: str) -> None:
        print("[DEBUG] enter PreReviewService._mark_project_failed | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        session = self.db_conn.get_session()
        try:
            row = (
                session.query(PreReviewProject)
                .filter(and_(PreReviewProject.project_id == project_id, PreReviewProject.is_deleted == 0))
                .first()
            )
            if row is not None:
                row.status = "failed"
                row.update_time = self._now()
                session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()

    def run_pre_review(self, project_id: str, source_doc_id: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        print("[DEBUG] enter PreReviewService.run_pre_review | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        session = self.db_conn.get_session()
        try:
            project = (
                session.query(PreReviewProject)
                .filter(and_(PreReviewProject.project_id == project_id, PreReviewProject.is_deleted == 0))
                .first()
            )
            if project is None:
                return False, "project not found", None

            ok, msg, chunks = self._load_doc_chunks(project_id=project_id, doc_id=source_doc_id)
            if not ok:
                return False, msg, None
            if not chunks:
                return False, "no chunk data for pre-review", None

            run_id = self._new_run_id()
            version = self._next_version(session, project_id)

            run_row = PreReviewRun(
                run_id=run_id,
                project_id=project_id,
                version_no=version,
                source_doc_id=source_doc_id,
                strategy="multi_agent_plan_and_solve+reflection",
                accuracy=None,
                summary="",
                create_time=self._now(),
                finish_time=None,
            )
            session.add(run_row)

            project.status = "running"
            project.progress = 0.1
            project.update_time = self._now()
            session.flush()

            # Seed memory before section review:
            # 1) historical feedback memory (episodic)
            self._seed_historical_feedback_memory(project_id=project_id)
            # 2) submission structure memory (semantic)
            ordered_chunks = self._order_review_units(chunks)
            self._seed_submission_structure_memory(
                project_id=project_id,
                source_doc_id=source_doc_id,
                review_units=ordered_chunks,
            )

            conclusions = []
            skipped_empty = 0
            previous_section_meta: Dict[str, Any] = {}
            for idx, chunk in enumerate(ordered_chunks):
                section_id = str(chunk.get("section_id") or chunk.get("chunk_id", idx + 1))
                section_code = str(chunk.get("section_code") or section_id)
                section_name = str(chunk.get("section_name") or chunk.get("title") or section_code or f"section-{section_id}")
                text = str(chunk.get("text", "")).strip()
                if not text:
                    skipped_empty += 1
                    continue

                # 2) rule memory (semantic) for current section
                section_query = self._build_section_query(
                    section_name=section_name,
                    section_code=section_code,
                    text=text,
                    title_path=chunk.get("title_path", []) if isinstance(chunk, dict) else [],
                )
                dynamic_top_k = max(4, min(8, len(text) // 1200 + 4))
                related_result = self.knowledge.semantic_query(section_query, top_k=dynamic_top_k, min_score=0.6)
                related = related_result.get("list", []) if isinstance(related_result, dict) else []
                linked_rules = [self._rule_label(x) for x in related]
                for ridx, r in enumerate(related):
                    rule_key = f"rule:{source_doc_id}:{section_id}:{ridx + 1}"
                    rule_text = f"{self._rule_label(r)} {r.get('content', '')}"
                    self.memory_tool.remember(
                        key=rule_key,
                        value=rule_text.strip(),
                        memory_type="semantic",
                        metadata={
                            "source": "rule",
                            "project_id": project_id,
                            "doc_id": source_doc_id,
                            "section_id": section_id,
                        },
                    )

                section_meta = {
                    "section_id": section_id,
                    "section_code": section_code,
                    "section_name": section_name,
                    "query": section_query,
                    "text_preview": self._preview(text, max_len=220),
                    "char_count": len(text),
                    "page": chunk.get("page"),
                    "page_start": chunk.get("page_start"),
                    "page_end": chunk.get("page_end"),
                    "unit_order": chunk.get("unit_order"),
                    "unit_type": chunk.get("unit_type"),
                    "parent_section_id": chunk.get("parent_section_id"),
                    "parent_code": chunk.get("parent_code"),
                    "title_path": chunk.get("title_path", []),
                    "previous_section_id": previous_section_meta.get("section_id", ""),
                    "previous_conclusion_preview": previous_section_meta.get("conclusion_preview", ""),
                }
                coordination_payload = self._build_coordination_payload(
                    project_id=project_id,
                    run_id=run_id,
                    source_doc_id=source_doc_id,
                    section_meta=section_meta,
                    related_result=related_result if isinstance(related_result, dict) else {},
                )

                # 3) run agent with injected memory context
                agent_out = self.agent.run(
                    source_doc_id,
                    section_id,
                    text,
                    related_rules=related,
                    coordination_payload=coordination_payload,
                    memory_metadata_filter={"project_id": project_id},
                )
                findings = agent_out.get("findings", [])
                score = float(agent_out.get("score", 0))

                # 4) recent working memory for next sections
                self.memory_tool.remember(
                    key=f"recent:{source_doc_id}:{section_id}",
                    value="; ".join(findings) if findings else "No obvious issue found",
                    memory_type="working",
                    metadata={
                        "source": "recent_finding",
                        "project_id": project_id,
                        "doc_id": source_doc_id,
                        "section_id": section_id,
                    },
                )

                conclusion_row = PreReviewSectionConclusion(
                    run_id=run_id,
                    section_id=section_id,
                    section_name=f"{section_code} {section_name}".strip(),
                    conclusion="; ".join(findings) if findings else "No obvious issue found",
                    highlighted_issues=json.dumps(findings, ensure_ascii=False),
                    linked_rules=json.dumps(linked_rules, ensure_ascii=False),
                    risk_level=self._classify_risk_level(findings=findings, score=score),
                    create_time=self._now(),
                )
                conclusions.append(conclusion_row)
                trace_payload = {
                    "coordination": coordination_payload,
                    "memory": {
                        "hit_count": len(agent_out.get("memory_hits", []) or []),
                        "context_preview": self._preview(agent_out.get("memory_context", ""), max_len=600),
                        "hits_by_type": (
                            agent_out.get("memory_package", {}).get("hits_by_type", {})
                            if isinstance(agent_out.get("memory_package"), dict)
                            else {}
                        ),
                    },
                    "agent": {
                        "strategy": agent_out.get("strategy", ""),
                        "roles": agent_out.get("agent_roles", []),
                        "findings_count": len(findings),
                        "score": score,
                    },
                    "trace": agent_out.get("trace", {}),
                }
                trace_row = PreReviewSectionTrace(
                    run_id=run_id,
                    section_id=section_id,
                    trace_json=json.dumps(trace_payload, ensure_ascii=False),
                    create_time=self._now(),
                )
                session.add(trace_row)
                previous_section_meta = {
                    "section_id": section_id,
                    "conclusion_preview": self._preview("; ".join(findings) if findings else "No obvious issue found"),
                }

            if not conclusions:
                raise ValueError("no non-empty sections after parsing")

            session.bulk_save_objects(conclusions)
            run_row.summary = f"Generated {len(conclusions)} section conclusions, skipped {skipped_empty} empty sections"
            run_row.finish_time = self._now()

            project.status = "completed"
            project.progress = 1.0
            project.update_time = self._now()

            session.commit()
            return True, "pre-review completed", {
                "run_id": run_id,
                "version_no": version,
                "conclusion_count": len(conclusions),
                "skipped_empty_count": skipped_empty,
            }
        except Exception as e:
            session.rollback()
            self._mark_project_failed(project_id)
            return False, f"run pre-review failed: {str(e)}", None
        finally:
            session.close()

    def _seed_historical_feedback_memory(self, project_id: str) -> None:
        """
        Load previous feedback in same project into episodic memory for context injection.
        """
        print("[DEBUG] enter PreReviewService._seed_historical_feedback_memory | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        session = self.db_conn.get_session()
        try:
            rows = (
                session.query(PreReviewFeedback, PreReviewRun)
                .join(PreReviewRun, PreReviewFeedback.run_id == PreReviewRun.run_id)
                .filter(PreReviewRun.project_id == project_id)
                .order_by(desc(PreReviewFeedback.id))
                .limit(200)
                .all()
            )
            for fb, run in rows:
                key = f"fb:{run.run_id}:{fb.id}"
                value = f"{fb.feedback_type} {fb.feedback_text or ''} {fb.suggestion or ''}".strip()
                self.memory_tool.remember(
                    key=key,
                    value=value,
                    memory_type="episodic",
                    metadata={
                        "source": "historical_feedback",
                        "project_id": project_id,
                        "run_id": run.run_id,
                        "section_id": fb.section_id or "",
                        "operator": fb.operator or "",
                    },
                )
        finally:
            session.close()

    def get_run_history(self, project_id: str) -> List[Dict[str, Any]]:
        print("[DEBUG] enter PreReviewService.get_run_history | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        session = self.db_conn.get_session()
        try:
            rows = (
                session.query(PreReviewRun)
                .filter(PreReviewRun.project_id == project_id)
                .order_by(desc(PreReviewRun.id))
                .all()
            )
            out = []
            for r in rows:
                feedback_count = session.query(PreReviewFeedback).filter(PreReviewFeedback.run_id == r.run_id).count()
                sub = (
                    session.query(PreReviewSubmissionFile)
                    .filter(PreReviewSubmissionFile.doc_id == r.source_doc_id)
                    .first()
                )
                out.append(
                    {
                        "run_id": r.run_id,
                        "project_id": r.project_id,
                        "version_no": r.version_no,
                        "source_doc_id": r.source_doc_id,
                        "source_file_name": sub.file_name if sub else "",
                        "strategy": r.strategy,
                        "accuracy": r.accuracy,
                        "summary": r.summary,
                        "feedback_count": feedback_count,
                        "create_time": r.create_time.strftime("%Y-%m-%d %H:%M:%S"),
                        "finish_time": r.finish_time.strftime("%Y-%m-%d %H:%M:%S") if r.finish_time else None,
                    }
                )
            return out
        finally:
            session.close()

    def get_section_conclusions(self, run_id: str, section_id: str = "") -> List[Dict[str, Any]]:
        print("[DEBUG] enter PreReviewService.get_section_conclusions | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        session = self.db_conn.get_session()
        try:
            def _safe_json_load(raw: Optional[str]) -> List[Any]:
                if not raw:
                    return []
                try:
                    data = json.loads(raw)
                    return data if isinstance(data, list) else []
                except Exception:
                    return []

            run_row = session.query(PreReviewRun).filter(PreReviewRun.run_id == run_id).first()
            query = session.query(PreReviewSectionConclusion).filter(PreReviewSectionConclusion.run_id == run_id)
            if section_id:
                query = query.filter(
                    and_(
                        PreReviewSectionConclusion.run_id == run_id,
                        (
                            (PreReviewSectionConclusion.section_id == section_id)
                            | (PreReviewSectionConclusion.section_name.like(f"{section_id}%"))
                        ),
                    )
                )
            rows = query.order_by(PreReviewSectionConclusion.id.asc()).all()
            out = [
                {
                    "run_id": r.run_id,
                    "section_id": r.section_id,
                    "section_name": r.section_name,
                    "conclusion": r.conclusion,
                    "highlighted_issues": _safe_json_load(r.highlighted_issues),
                    "linked_rules": _safe_json_load(r.linked_rules),
                    "risk_level": r.risk_level,
                    "create_time": r.create_time.strftime("%Y-%m-%d %H:%M:%S"),
                }
                for r in rows
            ]
            if (not section_id) and run_row is not None:
                ok, _, payload = self.get_submission_sections(
                    project_id=run_row.project_id,
                    doc_id=run_row.source_doc_id,
                )
                if ok and isinstance(payload, dict):
                    units = payload.get("review_units", [])
                    if isinstance(units, list):
                        order_map: Dict[str, int] = {}
                        for i, u in enumerate(units, start=1):
                            if not isinstance(u, dict):
                                continue
                            sid = str(u.get("section_id") or u.get("chunk_id") or "").strip()
                            if sid and sid not in order_map:
                                order_map[sid] = i
                        if order_map:
                            out = sorted(
                                out,
                                key=lambda x: (
                                    int(order_map.get(str(x.get("section_id", "")), 10**9)),
                                    str(x.get("section_id", "")),
                                ),
                            )
            return out
        finally:
            session.close()

    def get_run_section_overview(self, run_id: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        print("[DEBUG] enter PreReviewService.get_run_section_overview | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        session = self.db_conn.get_session()
        try:
            run = session.query(PreReviewRun).filter(PreReviewRun.run_id == run_id).first()
            if run is None:
                return False, "run not found", None

            ok, msg, section_payload = self.get_submission_sections(
                project_id=run.project_id,
                doc_id=run.source_doc_id,
            )
            if not ok:
                return False, msg, None

            conclusions = self.get_section_conclusions(run_id=run_id, section_id="")
            conclusion_by_section = {str(x.get("section_id")): x for x in conclusions}
            traces = self.get_section_traces(run_id=run_id, section_id="")
            trace_digest_by_section = {}
            for t in traces:
                sid = str(t.get("section_id", ""))
                if not sid:
                    continue
                coordination = t.get("coordination", {}) if isinstance(t.get("coordination"), dict) else {}
                retrieval = coordination.get("retrieval", {}) if isinstance(coordination.get("retrieval"), dict) else {}
                agent_meta = t.get("agent", {}) if isinstance(t.get("agent"), dict) else {}
                memory_meta = t.get("memory", {}) if isinstance(t.get("memory"), dict) else {}
                trace_digest_by_section[sid] = {
                    "trace_schema": t.get("trace_schema", "legacy"),
                    "retrieval_hit_count": retrieval.get("hit_count", 0),
                    "grouped_doc_count": retrieval.get("grouped_doc_count", 0),
                    "memory_hit_count": memory_meta.get("hit_count", 0),
                    "findings_count": agent_meta.get("findings_count", 0),
                    "score": agent_meta.get("score", 0.0),
                }

            return True, "success", {
                "run_id": run_id,
                "project_id": run.project_id,
                "source_doc_id": run.source_doc_id,
                "chapter_structure": section_payload.get("chapter_structure", []),
                "sections": section_payload.get("sections", []),
                "leaf_sibling_groups": section_payload.get("leaf_sibling_groups", []),
                "review_units": section_payload.get("review_units", []),
                "conclusion_by_section_id": conclusion_by_section,
                "trace_digest_by_section_id": trace_digest_by_section,
                "conclusions": conclusions,
            }
        finally:
            session.close()

    def get_section_traces(self, run_id: str, section_id: str = "") -> List[Dict[str, Any]]:
        print("[DEBUG] enter PreReviewService.get_section_traces | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        session = self.db_conn.get_session()
        try:
            query = session.query(PreReviewSectionTrace).filter(PreReviewSectionTrace.run_id == run_id)
            if section_id:
                query = query.filter(PreReviewSectionTrace.section_id == section_id)
            rows = query.order_by(PreReviewSectionTrace.id.asc()).all()

            out: List[Dict[str, Any]] = []
            for r in rows:
                try:
                    raw_trace = json.loads(r.trace_json) if r.trace_json else {}
                except Exception:
                    raw_trace = {}
                if isinstance(raw_trace, dict) and "trace" in raw_trace:
                    trace_schema = "coordination_v1"
                    coordination = raw_trace.get("coordination", {})
                    memory = raw_trace.get("memory", {})
                    trace = raw_trace.get("trace", {})
                    agent = raw_trace.get("agent", {})
                else:
                    trace_schema = "legacy"
                    coordination = {}
                    memory = {}
                    trace = raw_trace if isinstance(raw_trace, dict) else {}
                    agent = {}
                out.append(
                    {
                        "run_id": r.run_id,
                        "section_id": r.section_id,
                        "trace_schema": trace_schema,
                        "coordination": coordination,
                        "memory": memory,
                        "agent": agent,
                        "trace": trace,
                        "create_time": r.create_time.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )
            return out
        finally:
            session.close()

    def get_dashboard_summary(self) -> Dict[str, Any]:
        print("[DEBUG] enter PreReviewService.get_dashboard_summary | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        session = self.db_conn.get_session()
        try:
            project_total = session.query(PreReviewProject).filter(PreReviewProject.is_deleted == 0).count()
            running_projects = (
                session.query(PreReviewProject)
                .filter(and_(PreReviewProject.is_deleted == 0, PreReviewProject.status == "running"))
                .count()
            )
            completed_projects = (
                session.query(PreReviewProject)
                .filter(and_(PreReviewProject.is_deleted == 0, PreReviewProject.status == "completed"))
                .count()
            )
            run_total = session.query(PreReviewRun).count()
            feedback_total = session.query(PreReviewFeedback).count()
            avg_acc = session.query(func.avg(PreReviewRun.accuracy)).scalar()

            recent_runs = (
                session.query(PreReviewRun)
                .order_by(desc(PreReviewRun.id))
                .limit(5)
                .all()
            )
            return {
                "project_total": project_total,
                "running_projects": running_projects,
                "completed_projects": completed_projects,
                "run_total": run_total,
                "feedback_total": feedback_total,
                "avg_accuracy": round(float(avg_acc), 4) if avg_acc is not None else None,
                "recent_runs": [
                    {
                        "run_id": r.run_id,
                        "project_id": r.project_id,
                        "source_doc_id": r.source_doc_id,
                        "accuracy": r.accuracy,
                        "create_time": r.create_time.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    for r in recent_runs
                ],
            }
        finally:
            session.close()

    def get_agent_roles(self) -> List[Dict[str, Any]]:
        print("[DEBUG] enter PreReviewService.get_agent_roles | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        if hasattr(self.agent, "describe_roles"):
            return self.agent.describe_roles()
        return []

    def export_report_word(self, run_id: str) -> Tuple[bool, str, Optional[str]]:
        print("[DEBUG] enter PreReviewService.export_report_word | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        session = self.db_conn.get_session()
        try:
            run = session.query(PreReviewRun).filter(PreReviewRun.run_id == run_id).first()
            if run is None:
                return False, "run not found", None

            sections = (
                session.query(PreReviewSectionConclusion)
                .filter(PreReviewSectionConclusion.run_id == run_id)
                .order_by(PreReviewSectionConclusion.id.asc())
                .all()
            )
            if not sections:
                return False, "no conclusions found", None

            doc = Document()
            doc.add_heading(f"Pre-review Report - {run.run_id}", 0)
            doc.add_paragraph(f"Project ID: {run.project_id}")
            doc.add_paragraph(f"Version: v{run.version_no}")
            doc.add_paragraph(f"Strategy: {run.strategy}")
            doc.add_paragraph(f"Generated At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            for sec in sections:
                doc.add_heading(f"{sec.section_name} ({sec.section_id})", level=2)
                doc.add_paragraph(f"Risk Level: {sec.risk_level}")
                doc.add_paragraph(f"Conclusion: {sec.conclusion}")
                issues = json.loads(sec.highlighted_issues) if sec.highlighted_issues else []
                rules = json.loads(sec.linked_rules) if sec.linked_rules else []
                doc.add_paragraph(f"Highlighted Issues: {', '.join(issues) if issues else 'None'}")
                doc.add_paragraph(f"Linked Rules: {', '.join(rules) if rules else 'None'}")

            output_path = os.path.join(REPORT_DIR, f"{run_id}.docx")
            doc.save(output_path)
            return True, "report exported", output_path
        except Exception as e:
            return False, f"export report failed: {str(e)}", None
        finally:
            session.close()

    def _compute_feedback_stats(self, session, run_id: str, section_id: str = "") -> Dict[str, Any]:
        print("[DEBUG] enter PreReviewService._compute_feedback_stats | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        query = session.query(PreReviewFeedback).filter(PreReviewFeedback.run_id == run_id)
        if section_id:
            query = query.filter(PreReviewFeedback.section_id == section_id)
        rows = query.all()

        metrics = feedback_metrics([x.feedback_type for x in rows])
        return {
            "run_id": run_id,
            "section_id": section_id or "",
            "feedback_total": int(metrics["feedback_total"]),
            "valid_count": int(metrics["tp_valid"]),
            "false_positive_count": int(metrics["fp_false_positive"]),
            "missed_count": int(metrics["fn_missed"]),
            "accuracy": metrics["accuracy"],
            "precision": metrics["precision"],
            "recall": metrics["recall"],
            "f1": metrics["f1"],
            "reward_score": metrics["reward_score"],
        }

    def _refresh_accuracy(self, session, run_id: str) -> Dict[str, Any]:
        print("[DEBUG] enter PreReviewService._refresh_accuracy | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        stats = self._compute_feedback_stats(session, run_id)
        run = session.query(PreReviewRun).filter(PreReviewRun.run_id == run_id).first()
        if run is not None:
            run.accuracy = stats["accuracy"] if stats["feedback_total"] > 0 else None
        return stats

    def _optimize_from_feedback_memory(
        self,
        run_id: str,
        section_id: str,
        feedback_type: str,
        feedback_text: str,
        suggestion: str,
        operator: str,
    ) -> None:
        print("[DEBUG] enter PreReviewService._optimize_from_feedback_memory | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        note = f"{feedback_type} | {feedback_text or ''} | {suggestion or ''}".strip(" |")
        if not note:
            return

        base_meta = {
            "source": "online_feedback",
            "run_id": run_id,
            "section_id": section_id or "",
            "operator": operator or "",
        }
        memory_type = "episodic"
        if feedback_type == "missed":
            memory_type = "semantic"
        elif feedback_type == "false_positive":
            memory_type = "working"

        self.memory_tool.remember(
            key=f"feedback:{run_id}:{section_id or 'global'}:{uuid.uuid4().hex[:8]}",
            value=note,
            memory_type=memory_type,
            metadata=base_meta,
        )

    def add_feedback(
        self,
        run_id: str,
        section_id: str,
        feedback_type: str,
        feedback_text: str = "",
        suggestion: str = "",
        operator: str = "",
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        print("[DEBUG] enter PreReviewService.add_feedback | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        if feedback_type not in {"valid", "false_positive", "missed"}:
            return False, "feedback_type must be one of valid/false_positive/missed", None

        session = self.db_conn.get_session()
        try:
            run = session.query(PreReviewRun).filter(PreReviewRun.run_id == run_id).first()
            if run is None:
                return False, "run not found", None

            if section_id:
                section_exists = (
                    session.query(PreReviewSectionConclusion)
                    .filter(
                        and_(
                            PreReviewSectionConclusion.run_id == run_id,
                            PreReviewSectionConclusion.section_id == section_id,
                        )
                    )
                    .first()
                )
                if section_exists is None:
                    return False, "section_id does not belong to this run", None

            fb = PreReviewFeedback(
                run_id=run_id,
                section_id=section_id or None,
                feedback_type=feedback_type,
                feedback_text=feedback_text,
                suggestion=suggestion,
                operator=operator,
                create_time=self._now(),
            )
            session.add(fb)
            session.flush()
            stats = self._refresh_accuracy(session, run_id)
            session.commit()
            self._optimize_from_feedback_memory(
                run_id=run_id,
                section_id=section_id,
                feedback_type=feedback_type,
                feedback_text=feedback_text,
                suggestion=suggestion,
                operator=operator,
            )
            return True, "feedback added", stats
        except Exception as e:
            session.rollback()
            return False, f"add feedback failed: {str(e)}", None
        finally:
            session.close()

    def get_feedback_stats(self, run_id: str, section_id: str = "") -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        print("[DEBUG] enter PreReviewService.get_feedback_stats | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        session = self.db_conn.get_session()
        try:
            run = session.query(PreReviewRun).filter(PreReviewRun.run_id == run_id).first()
            if run is None:
                return False, "run not found", None

            stats = self._compute_feedback_stats(session, run_id=run_id, section_id=section_id)
            return True, "success", stats
        except Exception as e:
            return False, f"get feedback stats failed: {str(e)}", None
        finally:
            session.close()
