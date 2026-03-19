import re
from typing import Any, Dict, List, Optional, Tuple

from agent.agent_backend.utils.parser import ParserManager
from agent.agent_backend.utils.parser.text_sanitizer import sanitize_parser_text


SECTION_LINE_RE = re.compile(r"(3\s*\.\s*2\s*\.\s*[SP](?:\s*\.\s*\d+){1,2})", re.IGNORECASE)
TITLE_SPLIT_RE = re.compile(r"[\s\u3000]+")
TOC_DOTS_RE = re.compile(r"[.\u2026\u00b7\u2022\-_]{3,}\s*\d{1,4}\s*$")


def _normalize_line(text: str) -> str:
    value = sanitize_parser_text(text).strip()
    value = re.sub(r"[ \t]+", " ", value)
    return value


def _flatten_catalog_nodes(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for node in nodes or []:
        if not isinstance(node, dict):
            continue
        out.append(node)
        out.extend(_flatten_catalog_nodes(node.get("children_sections") or []))
    return out


def _catalog_branch(catalog: Dict[str, Any], root_section_id: str) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    roots = catalog.get("chapter_structure", []) if isinstance(catalog, dict) else []
    branch = next(
        (
            node
            for node in roots
            if isinstance(node, dict) and str(node.get("section_id", "")).strip() == str(root_section_id or "").strip()
        ),
        None,
    )
    if not branch:
        return [], {}
    flat = _flatten_catalog_nodes(branch.get("children_sections") or [])
    return flat, {str(item.get("section_id", "")).strip(): item for item in flat if str(item.get("section_id", "")).strip()}


def _iter_ordered_lines(file_path: str, ext_hint: str = "") -> List[Dict[str, Any]]:
    rows = ParserManager.parse(file_path, ext_hint=ext_hint)
    lines: List[Dict[str, Any]] = []
    for row_index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        text = sanitize_parser_text(row.get("text", ""))
        page = row.get("page")
        for line_index, raw_line in enumerate(text.split("\n"), start=1):
            line = _normalize_line(raw_line)
            if not line:
                continue
            lines.append(
                {
                    "text": line,
                    "page": page,
                    "row_index": row_index,
                    "line_index": line_index,
                }
            )
    return lines


def _extract_title_from_line(line: str, section_id: str) -> str:
    value = _normalize_line(line)
    if not value:
        return ""
    if value.lower().startswith(section_id.lower()):
        tail = value[len(section_id):].strip(" \t-:.")
        return tail.strip()
    return value


def _line_matches_section(line: str, section_id: str, section_name: str, next_line: str = "") -> bool:
    value = _normalize_line(line)
    if not value:
        return False
    match = SECTION_LINE_RE.search(value)
    if not match:
        return False
    matched_token = _normalized_section_token(match.group(1))
    target_token = _normalized_section_token(section_id)
    if matched_token != target_token:
        return False
    if TOC_DOTS_RE.search(value):
        return False
    if not section_name:
        return True
    tail = _extract_title_from_line(value, section_id)
    compact_tail = _compact_title(tail)
    compact_name = _compact_title(section_name)
    if not compact_name:
        return True
    if compact_tail and (compact_name in compact_tail or compact_tail in compact_name):
        return True
    compact_next = _compact_title(next_line)
    if compact_next and (compact_name in compact_next or compact_next in compact_name):
        return True
    return not bool(compact_tail)


def _detect_heading_hits(lines: List[Dict[str, Any]], flat_sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    hits: List[Dict[str, Any]] = []
    cursor = 0
    used_indexes: set[int] = set()
    for item in flat_sections:
        section_id = str(item.get("section_id", "")).strip()
        section_name = str(item.get("section_name", "")).strip()
        if not section_id:
            continue
        found_at: Optional[int] = None
        for idx in range(cursor, len(lines)):
            if idx in used_indexes:
                continue
            next_line = str(lines[idx + 1].get("text", "")) if idx + 1 < len(lines) else ""
            if _line_matches_section(str(lines[idx].get("text", "")), section_id, section_name, next_line=next_line):
                found_at = idx
                break
        if found_at is None and section_name:
            compact_name = _compact_title(section_name)
            for idx in range(cursor, len(lines)):
                if idx in used_indexes:
                    continue
                value = _normalize_line(str(lines[idx].get("text", "")))
                if TOC_DOTS_RE.search(value):
                    continue
                if _compact_title(value) == compact_name:
                    found_at = idx
                    break
        if found_at is None:
            continue
        hit_line = lines[found_at]
        hit_title = _extract_title_from_line(str(hit_line.get("text", "")), section_id) or section_name
        if (not hit_title or _compact_title(hit_title) == _normalized_section_token(section_id)) and found_at + 1 < len(lines):
            next_line = str(lines[found_at + 1].get("text", ""))
            if next_line and not SECTION_LINE_RE.search(next_line):
                hit_title = next_line
        hits.append(
            {
                "section_id": section_id,
                "section_code": str(item.get("section_code", section_id)).strip() or section_id,
                "section_name": section_name or section_id,
                "title_path": list(item.get("title_path") or []),
                "parent_section_id": str(item.get("parent_section_id", "") or "").strip(),
                "start_index": found_at,
                "page": hit_line.get("page"),
                "heading": str(hit_line.get("text", "")),
                "heading_title": hit_title or section_name or section_id,
            }
        )
        used_indexes.add(found_at)
        cursor = found_at + 1
    return hits


def _slice_sections(lines: List[Dict[str, Any]], hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    sections: List[Dict[str, Any]] = []
    for idx, hit in enumerate(hits):
        start = int(hit.get("start_index", 0)) + 1
        end = int(hits[idx + 1].get("start_index", len(lines))) if idx + 1 < len(hits) else len(lines)
        body_lines = [str(item.get("text", "")).strip() for item in lines[start:end] if str(item.get("text", "")).strip()]
        content = "\n".join(body_lines).strip()
        sections.append(
            {
                "section_id": str(hit.get("section_id", "")).strip(),
                "code": str(hit.get("section_code", "")).strip() or str(hit.get("section_id", "")).strip(),
                "title": str(hit.get("section_name", "")).strip() or str(hit.get("section_id", "")).strip(),
                "section_name": str(hit.get("section_name", "")).strip() or str(hit.get("section_id", "")).strip(),
                "title_path": list(hit.get("title_path") or []),
                "parent_section_id": str(hit.get("parent_section_id", "")).strip(),
                "page_start": hit.get("page"),
                "page_end": lines[end - 1].get("page") if end > start and end - 1 < len(lines) else hit.get("page"),
                "heading": str(hit.get("heading", "")),
                "content": content,
                "content_preview": content[:320],
                "char_count": len(content),
            }
        )
    return sections


def _build_chapter_tree(
    nodes: List[Dict[str, Any]],
    content_map: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for node in nodes or []:
        if not isinstance(node, dict):
            continue
        section_id = str(node.get("section_id", "")).strip()
        matched = content_map.get(section_id, {})
        out.append(
            {
                "section_id": section_id,
                "section_code": str(node.get("section_code", section_id)).strip() or section_id,
                "section_name": str(node.get("section_name", "")).strip() or section_id,
                "title_path": list(node.get("title_path") or []),
                "content": str(matched.get("content", "") or ""),
                "content_preview": str(matched.get("content_preview", "") or ""),
                "char_count": int(matched.get("char_count", 0) or 0),
                "children_sections": _build_chapter_tree(node.get("children_sections") or [], content_map),
            }
        )
    return out


def parse_strict_ctd_submission(
    file_path: str,
    catalog: Dict[str, Any],
    root_section_id: str,
    ext_hint: str = "",
) -> Dict[str, Any]:
    flat_sections, section_map = _catalog_branch(catalog, root_section_id)
    if not flat_sections:
        return {
            "root_section_id": root_section_id,
            "chapter_structure": [],
            "sections": [],
            "review_units": [],
            "statistics": {"matched_section_total": 0},
        }

    lines = _iter_ordered_lines(file_path=file_path, ext_hint=ext_hint)
    hits = _detect_heading_hits(lines=lines, flat_sections=flat_sections)
    sections = _slice_sections(lines=lines, hits=hits)
    content_map = {str(item.get("section_id", "")).strip(): item for item in sections}
    branch_root = next(
        (
            node
            for node in (catalog.get("chapter_structure", []) if isinstance(catalog, dict) else [])
            if isinstance(node, dict) and str(node.get("section_id", "")).strip() == str(root_section_id or "").strip()
        ),
        None,
    )
    branch_children = branch_root.get("children_sections", []) if isinstance(branch_root, dict) else []
    chapter_structure = _build_chapter_tree(branch_children, content_map)

    review_units: List[Dict[str, Any]] = []
    for order, section in enumerate(sections, start=1):
        text = str(section.get("content", "")).strip()
        if not text:
            continue
        sid = str(section.get("section_id", "")).strip()
        meta = section_map.get(sid, {})
        review_units.append(
            {
                "chunk_id": sid,
                "section_id": sid,
                "section_code": str(section.get("code", sid)).strip() or sid,
                "section_name": str(section.get("section_name", sid)).strip() or sid,
                "parent_section_id": str(meta.get("parent_section_id", "")).strip(),
                "page": section.get("page_start"),
                "page_start": section.get("page_start"),
                "page_end": section.get("page_end"),
                "text": text,
                "title_path": list(section.get("title_path") or []),
                "unit_order": order,
                "unit_type": "strict_ctd_section",
            }
        )

    return {
        "root_section_id": root_section_id,
        "chapter_structure": chapter_structure,
        "sections": sections,
        "review_units": review_units,
        "statistics": {
            "line_total": len(lines),
            "matched_section_total": len(sections),
            "review_unit_total": len(review_units),
        },
    }
