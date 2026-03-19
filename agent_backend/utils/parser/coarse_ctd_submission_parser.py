from __future__ import annotations

import copy
import importlib.util
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.agent_backend.config.settings import settings


@lru_cache(maxsize=1)
def _load_ctd_parse_module():
    module_path = Path(__file__).resolve().parents[2] / "test" / "ctd_parse.py"
    spec = importlib.util.spec_from_file_location("agent_backend_test_ctd_parse", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"unable to load ctd_parse module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def _load_ocr_client(module: Any):
    client_cls = getattr(module, "OCRServiceClient", None)
    base_url = str(settings.ocr_service_url or "").strip()
    if client_cls is None or not base_url:
        return None
    try:
        client = client_cls(base_url, timeout=int(settings.ocr_timeout_seconds))
        if hasattr(client, "healthcheck") and client.healthcheck():
            return client
    except Exception:
        return None
    return None


def _section_tree_for_root(catalog: Dict[str, Any], root_section_id: str) -> List[Dict[str, Any]]:
    roots = catalog.get("chapter_structure", []) if isinstance(catalog, dict) else []
    for node in roots:
        if not isinstance(node, dict):
            continue
        if str(node.get("section_id", "")).strip() == str(root_section_id or "").strip():
            return copy.deepcopy(node.get("children_sections") or [])
    return []


def _normalize_title_path(node: Dict[str, Any], section_meta: Optional[Dict[str, Any]], parent_titles: List[str]) -> List[str]:
    if section_meta and isinstance(section_meta.get("title_path"), list):
        return [str(x).strip() for x in section_meta.get("title_path", []) if str(x).strip()]
    current_title = str(node.get("section_name") or node.get("section_title") or node.get("section_id") or "").strip()
    return [*parent_titles, current_title] if current_title else list(parent_titles)


def _convert_tree(
    nodes: List[Dict[str, Any]],
    section_map: Dict[str, Dict[str, Any]],
    parent_section_id: str = "",
    parent_titles: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    parent_titles = parent_titles or []
    out: List[Dict[str, Any]] = []
    for node in nodes or []:
        if not isinstance(node, dict):
            continue
        section_id = str(node.get("section_id", "") or "").strip()
        if not section_id:
            continue
        section_meta = section_map.get(section_id, {}) if isinstance(section_map, dict) else {}
        section_name = str(section_meta.get("section_name") or node.get("section_name") or node.get("section_title") or section_id).strip()
        title_path = _normalize_title_path(node, section_meta, parent_titles)
        raw_pages = [int(x) for x in (node.get("raw_pages") or []) if str(x).strip().isdigit()]
        content = str(node.get("content") or "").strip()
        children = _convert_tree(
            node.get("children_sections") or [],
            section_map=section_map,
            parent_section_id=section_id,
            parent_titles=title_path,
        )
        out.append(
            {
                "section_id": section_id,
                "section_code": str(section_meta.get("section_code") or section_id).strip() or section_id,
                "section_name": section_name,
                "title_path": title_path,
                "parent_section_id": parent_section_id,
                "page_start": min(raw_pages) if raw_pages else None,
                "page_end": max(raw_pages) if raw_pages else None,
                "raw_pages": raw_pages,
                "content": content,
                "content_preview": content[:320],
                "char_count": len(content),
                "tables": node.get("tables") or [],
                "children_sections": children,
            }
        )
    return out


def _flatten_tree(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for node in nodes or []:
        if not isinstance(node, dict):
            continue
        out.append({k: v for k, v in node.items() if k != "children_sections"})
        out.extend(_flatten_tree(node.get("children_sections") or []))
    return out


def parse_coarse_ctd_submission(
    file_path: str,
    catalog: Dict[str, Any],
    root_section_id: str,
) -> Dict[str, Any]:
    root = str(root_section_id or "").strip()
    if root not in {"3.2.S", "3.2.P"}:
        return {
            "root_section_id": root,
            "structure_type": "ctd_fixed_outline_coarse_payload_v1",
            "chapter_structure": [],
            "sections": [],
            "review_units": [],
            "statistics": {"matched_section_total": 0, "review_unit_total": 0},
        }

    module = _load_ctd_parse_module()
    outline = module.get_outline("S" if root == "3.2.S" else "P")
    ocr_client = _load_ocr_client(module)
    parsed = module.parse_pdf_to_markdown_json(
        pdf_path=Path(file_path),
        outline=outline,
        text_source="auto" if ocr_client is not None else "pdf",
        ocr_lang=settings.ocr_lang,
        ocr_client=ocr_client,
        embed_images=False,
        title=f"{root} coarse parse",
    )

    section_map = catalog.get("section_map", {}) if isinstance(catalog, dict) else {}
    chapter_structure = _convert_tree(
        parsed.get("sections") or [],
        section_map=section_map,
        parent_section_id=root,
        parent_titles=[str(root)],
    )
    sections = _flatten_tree(chapter_structure)

    review_units: List[Dict[str, Any]] = []
    for order, item in enumerate(sections, start=1):
        text = str(item.get("content") or "").strip()
        if not text:
            continue
        section_id = str(item.get("section_id") or "").strip()
        section_code = str(item.get("section_code") or section_id).strip() or section_id
        section_name = str(item.get("section_name") or section_id).strip() or section_id
        review_units.append(
            {
                "chunk_id": section_id,
                "section_id": section_id,
                "section_code": section_code,
                "section_name": section_name,
                "parent_section_id": str(item.get("parent_section_id") or "").strip(),
                "page": item.get("page_start"),
                "page_start": item.get("page_start"),
                "page_end": item.get("page_end"),
                "text": text,
                "title_path": list(item.get("title_path") or []),
                "char_count": len(text),
                "unit_order": order,
                "unit_type": "ctd_coarse_section",
                "pipeline": "ctd_outline_coarse",
            }
        )

    return {
        "root_section_id": root,
        "structure_type": "ctd_fixed_outline_coarse_payload_v1",
        "source_pdf": str(file_path),
        "chapter_structure": chapter_structure,
        "sections": sections,
        "review_units": review_units,
        "anchors": parsed.get("anchors") or [],
        "pages": parsed.get("pages") or {},
        "statistics": {
            "matched_section_total": len(sections),
            "review_unit_total": len(review_units),
        },
    }

