from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fitz

CN_NUM = "一二三四五六七八九十百千零"


def str2bool(v: str) -> bool:
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}


def normalize_text(s: str) -> str:
    if s is None:
        return ""
    s = str(s)
    s = s.replace("\u3000", " ").replace("\xa0", " ")
    s = s.replace("［", "[").replace("］", "]")
    s = s.replace("（", "(").replace("）", ")")
    s = s.replace("：", ":")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\s+\n", "\n", s)
    s = re.sub(r"\n\s+", "\n", s)
    return s.strip()


def escape_md(text: str) -> str:
    return str(text).replace("\n", " ").strip().replace("|", "\\|")


def safe_filename(name: str) -> str:
    name = re.sub(r"[\\/:*?\"<>|]+", "_", name)
    name = re.sub(r"\s+", "_", name).strip("_")
    return name or "image"


def image_to_base64(pix: fitz.Pixmap) -> str:
    return base64.b64encode(pix.tobytes("png")).decode("utf-8")


def crop_pixmap(page: fitz.Page, bbox: List[float], zoom: float = 2.2) -> fitz.Pixmap:
    rect = fitz.Rect(bbox)
    return page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=rect, alpha=False)


def bbox_overlap(b1: List[float], b2: List[float]) -> bool:
    return not (b1[2] < b2[0] or b1[0] > b2[2] or b1[3] < b2[1] or b1[1] > b2[3])


@dataclass
class HeadingInfo:
    level: int
    title: str
    number: str = ""
    kind: str = "generic"


def strip_trailing_colon(text: str) -> str:
    return re.sub(r"[:：]\s*$", "", text).strip()


def extract_heading_info(text: str) -> Optional[HeadingInfo]:
    t = strip_trailing_colon(normalize_text(text))
    if not t:
        return None

    m = re.match(r"^(3\.2\.[SP]\.(?:\d+)(?:\.\d+)*)\s+(.+)$", t, re.I)
    if m:
        depth = m.group(1).count(".") - 2
        return HeadingInfo(level=min(6, 2 + depth), title=t, number=m.group(1), kind="ctd")
    m = re.match(r"^(3\.2\.[SP]\.(?:\d+)(?:\.\d+)*)$", t, re.I)
    if m:
        depth = m.group(1).count(".") - 2
        return HeadingInfo(level=min(6, 2 + depth), title=t, number=m.group(1), kind="ctd")

    m = re.match(rf"^([{CN_NUM}]+)[、.]\s*(.+)$", t)
    if m:
        return HeadingInfo(level=1, title=t, number=m.group(1), kind="cn1")

    m = re.match(rf"^\(([{CN_NUM}]+)\)\s*(.+)$", t)
    if m:
        return HeadingInfo(level=2, title=t, number=m.group(1), kind="cn2")

    m = re.match(r"^(\d+)[、.]\s*(.+)$", t)
    if m:
        return HeadingInfo(level=3, title=t, number=m.group(1), kind="arabic1")
    m = re.match(r"^(\d+)\s+(.+)$", t)
    if m and len(m.group(2)) <= 60:
        return HeadingInfo(level=3, title=t, number=m.group(1), kind="arabic1_space")

    m = re.match(r"^(\d+(?:\.\d+){1,5})\s+(.+)$", t)
    if m:
        lvl = min(6, 3 + m.group(1).count("."))
        return HeadingInfo(level=lvl, title=t, number=m.group(1), kind="arabic_multi")
    m = re.match(r"^(\d+(?:\.\d+){1,5})$", t)
    if m:
        lvl = min(6, 3 + m.group(1).count("."))
        return HeadingInfo(level=lvl, title=t, number=m.group(1), kind="arabic_multi")

    if re.match(r"^(附件|附录)\s*[A-Za-z0-9一二三四五六七八九十]+[:：]?\s*.*$", t):
        return HeadingInfo(level=1, title=t, number="", kind="appendix")
    if re.match(r"^[\[【]?(参考文献|名词解释|名词术语|术语|申报资料要求|沟通交流|注册检验)[\]】]?$", t):
        return HeadingInfo(level=1, title=t, number="", kind="tail")

    m = re.match(r"^((?:chapter|section|appendix)\s+[A-Za-z0-9IVXivx]+)\b(.*)$", t, re.I)
    if m:
        return HeadingInfo(level=2, title=t, number=m.group(1), kind="en")
    return None


TOC_HINT_PATTERNS = [re.compile(r"^目\s*录$"), re.compile(r"^contents$", re.I)]
TOC_LINE_PATTERNS = [
    re.compile(r"^.+\.{2,}\s*\d+\s*$"),
    re.compile(rf"^[{CN_NUM}]+[、.]\s*.+\.{2,}\s*\d+\s*$"),
    re.compile(rf"^\([{CN_NUM}]+\)\s*.+\.{2,}\s*\d+\s*$"),
    re.compile(r"^\d+(?:\.\d+)*\s+.+\.{2,}\s*\d+\s*$"),
]
HEADER_FOOTER_PATTERNS = [
    re.compile(r"^国家药品监督管理局药品审评中心$"),
    re.compile(r"^\d{4}\s*年\s*\d{1,2}\s*月$"),
    re.compile(r"^第?\s*\d+\s*页$"),
    re.compile(r"^\d+\s*/\s*\d+$"),
    re.compile(r"^\d+$"),
]


def is_header_or_footer(text: str, page_height: float, bbox: List[float]) -> bool:
    t = normalize_text(text)
    if not t:
        return True
    y0, y1 = bbox[1], bbox[3]
    near_top = y0 < page_height * 0.08
    near_bottom = y1 > page_height * 0.92
    return (near_top or near_bottom) and any(p.match(t) for p in HEADER_FOOTER_PATTERNS)


def is_toc_page(lines: List[Dict[str, Any]]) -> bool:
    texts = [normalize_text(x.get("text", "")) for x in lines if normalize_text(x.get("text", ""))]
    if not texts:
        return False
    has_toc_title = any(any(p.match(t) for p in TOC_HINT_PATTERNS) for t in texts[:8])
    toc_line_count = sum(1 for t in texts if any(p.match(t) for p in TOC_LINE_PATTERNS))
    return has_toc_title or toc_line_count >= max(4, len(texts) // 3)


def is_probable_heading(text: str, page_width: float, bbox: List[float], font_size_hint: Optional[float]) -> bool:
    t = strip_trailing_colon(normalize_text(text))
    if not t or len(t) > 120:
        return False
    info = extract_heading_info(t)
    if info is None:
        return False
    x0, _, x1, _ = bbox
    width = x1 - x0
    if width > page_width * 0.93 and len(t) > 35 and info.kind not in {"ctd", "tail"}:
        return False
    if x0 > page_width * 0.3 and info.kind not in {"tail"}:
        return False
    if font_size_hint is not None:
        if info.level <= 2 and font_size_hint < 8.5:
            return False
        if info.kind == "arabic1_space" and font_size_hint < 8.0:
            return False
    if t.endswith(("。", "；", ";", "，", ",")):
        return False
    return True


def should_merge_heading_with_next(cur_text: str, next_text: str) -> bool:
    cur = normalize_text(cur_text)
    nxt = normalize_text(next_text)
    if not cur or not nxt:
        return False
    if extract_heading_info(strip_trailing_colon(cur)) is None:
        return False
    if extract_heading_info(strip_trailing_colon(nxt)) is not None:
        return False
    if len(nxt) > 40:
        return False
    if re.search(r"[。；;，,]$", nxt):
        return False
    return True


def extract_page_lines(page: fitz.Page) -> List[Dict[str, Any]]:
    words = page.get_text("words")
    if not words:
        return []
    rows: Dict[float, List[Any]] = {}
    for w in words:
        x0, y0, x1, y1, text, *_ = w
        rows.setdefault(round(y0, 1), []).append((x0, y0, x1, y1, text))
    line_objs: List[Dict[str, Any]] = []
    for key in sorted(rows.keys()):
        row_words = sorted(rows[key], key=lambda t: t[0])
        x0 = min(w[0] for w in row_words)
        y0 = min(w[1] for w in row_words)
        x1 = max(w[2] for w in row_words)
        y1 = max(w[3] for w in row_words)
        line_text = " ".join(w[4] for w in row_words).strip()
        line_objs.append({"type": "line", "text": normalize_text(line_text), "bbox": [x0, y0, x1, y1], "words": row_words})
    return merge_wrapped_lines(line_objs)


def merge_wrapped_lines(lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not lines:
        return []
    merged = [lines[0]]
    for cur in lines[1:]:
        prev = merged[-1]
        gap = cur["bbox"][1] - prev["bbox"][3]
        same_block = gap < 5
        prev_text = prev["text"]
        cur_text = cur["text"]
        prev_is_heading = extract_heading_info(strip_trailing_colon(prev_text)) is not None
        cur_is_heading = extract_heading_info(strip_trailing_colon(cur_text)) is not None
        should_merge = same_block and prev_text and cur_text and not prev_is_heading and not cur_is_heading and not prev_text.endswith(("。", "；", ":", ".", "）", ")", "!", "?", "！", "？", "|")) and len(cur_text) < 80
        if should_merge:
            prev["text"] = normalize_text(prev["text"] + " " + cur["text"])
            prev["bbox"] = [min(prev["bbox"][0], cur["bbox"][0]), min(prev["bbox"][1], cur["bbox"][1]), max(prev["bbox"][2], cur["bbox"][2]), max(prev["bbox"][3], cur["bbox"][3])]
            prev["words"].extend(cur["words"])
        else:
            merged.append(cur)
    return merged


def extract_font_hints(page: fitz.Page) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    data = page.get_text("dict")
    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue
            text = normalize_text("".join(s.get("text", "") for s in spans))
            if not text:
                continue
            bbox = list(line.get("bbox", [0, 0, 0, 0]))
            size = max((float(s.get("size", 0)) for s in spans), default=0)
            result.append({"text": text, "bbox": bbox, "size": size})
    return result


def find_font_hint_for_line(line: Dict[str, Any], font_lines: List[Dict[str, Any]]) -> Optional[float]:
    lb = line["bbox"]
    best = None
    best_overlap = -1.0
    for f in font_lines:
        fb = f["bbox"]
        ix0 = max(lb[0], fb[0])
        iy0 = max(lb[1], fb[1])
        ix1 = min(lb[2], fb[2])
        iy1 = min(lb[3], fb[3])
        if ix1 <= ix0 or iy1 <= iy0:
            continue
        area = (ix1 - ix0) * (iy1 - iy0)
        if area > best_overlap:
            best_overlap = area
            best = f
    return best["size"] if best else None


def split_columns_from_words(line: Dict[str, Any], gap_threshold: float = 16.0) -> List[str]:
    words = sorted(line["words"], key=lambda t: t[0])
    if not words:
        return []
    cells: List[List[str]] = [[words[0][4]]]
    prev_x1 = words[0][2]
    for w in words[1:]:
        if w[0] - prev_x1 > gap_threshold:
            cells.append([w[4]])
        else:
            cells[-1].append(w[4])
        prev_x1 = w[2]
    return [normalize_text(" ".join(c)) for c in cells if normalize_text(" ".join(c))]


def split_columns_by_spaces(text: str) -> List[str]:
    return [x.strip() for x in re.split(r"\s{2,}", text) if x.strip()]


def markdown_table(columns: List[str], data: List[List[str]]) -> str:
    if not columns:
        return ""
    rows = ["| " + " | ".join(escape_md(c) for c in columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in data:
        row = row + [""] * (len(columns) - len(row))
        rows.append("| " + " | ".join(escape_md(c) for c in row[:len(columns)]) + " |")
    return "\n".join(rows)


def is_tableish_text(text: str) -> bool:
    t = normalize_text(text)
    if not t or extract_heading_info(strip_trailing_colon(t)) is not None:
        return False
    score = 0
    if re.search(r"(规格|持证商|备注|项目|内容|成分|浓度|批量|生产商|执行标准|序号|英文名称|质量标准)", t):
        score += 2
    if len(re.findall(r"\s{2,}", t)) >= 1:
        score += 1
    if len(split_columns_by_spaces(t)) >= 3:
        score += 1
    if re.search(r"\b\d+(?:\.\d+)?[%mMcCiGBq/\-~]*\b", t):
        score += 1
    return score >= 2


def detect_table_candidates(lines: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    groups: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []
    for line in lines:
        if is_tableish_text(line["text"]):
            current.append(line)
        else:
            if len(current) >= 2:
                groups.append(current)
            current = []
    if len(current) >= 2:
        groups.append(current)
    return groups


def group_bbox(group: List[Dict[str, Any]]) -> List[float]:
    return [min(g["bbox"][0] for g in group), min(g["bbox"][1] for g in group), max(g["bbox"][2] for g in group), max(g["bbox"][3] for g in group)]


def table_group_to_frame(group: List[Dict[str, Any]], page_num: int, table_idx: int) -> Optional[Dict[str, Any]]:
    rows: List[List[str]] = []
    for line in group:
        cols = split_columns_from_words(line)
        if len(cols) < 2:
            cols = split_columns_by_spaces(line["text"])
        if cols:
            rows.append(cols)
    if len(rows) < 2:
        return None
    max_cols = max(len(r) for r in rows)
    if max_cols < 2:
        return None
    norm_rows = [r + [""] * (max_cols - len(r)) for r in rows]
    columns = norm_rows[0]
    data = norm_rows[1:]
    return {"id": f"tbl_p{page_num}_{table_idx}", "type": "frame", "source": "text_table", "page": page_num, "bbox": group_bbox(group), "columns": columns, "data": data, "markdown": markdown_table(columns, data)}


def line_in_any_group(line: Dict[str, Any], groups: List[List[Dict[str, Any]]]) -> bool:
    return any(bbox_overlap(line["bbox"], group_bbox(g)) for g in groups)


def get_image_blocks(page: fitz.Page, min_width: float, min_height: float) -> List[Dict[str, Any]]:
    info = page.get_text("dict")
    blocks = info.get("blocks", [])
    res: List[Dict[str, Any]] = []
    idx = 0
    for b in blocks:
        if b.get("type") != 1:
            continue
        bbox = b.get("bbox")
        if not bbox:
            continue
        x0, y0, x1, y1 = bbox
        w = x1 - x0
        h = y1 - y0
        if w < min_width or h < min_height:
            continue
        idx += 1
        res.append({"type": "image_block", "bbox": [x0, y0, x1, y1], "width": w, "height": h, "index": idx})
    return res


def nearby_caption(lines: List[Dict[str, Any]], bbox: List[float], max_gap: float = 30.0) -> str:
    x0, y0, x1, y1 = bbox
    candidates = []
    for line in lines:
        lx0, ly0, lx1, ly1 = line["bbox"]
        vertical_near = (0 <= ly0 - y1 <= max_gap) or (0 <= y0 - ly1 <= max_gap)
        horizontal_overlap = not (lx1 < x0 or lx0 > x1)
        if vertical_near and horizontal_overlap:
            txt = line["text"]
            if re.search(r"^(图|表|figure|table)\s*[:：\d一二三四五六七八九十A-Za-z_\-\[\]]*", txt, re.I):
                candidates.append(txt)
    return normalize_text(" ".join(candidates))


def markdownize_text_line(text: str) -> str:
    text = normalize_text(text)
    if not text:
        return ""
    m = re.match(r"^\((\d+)\)\s*(.+)$", text)
    if m:
        return f"1. {m.group(2).strip()}"
    m = re.match(rf"^([{CN_NUM}]+[、.])\s*(.+)$", text)
    if m:
        return f"- {m.group(2).strip()}"
    m = re.match(r"^([\-•·●])\s*(.+)$", text)
    if m:
        return f"- {m.group(2).strip()}"
    return text


def compact_markdown_parts(parts: List[Dict[str, str]]) -> str:
    blocks: List[str] = []
    text_buffer: List[str] = []

    def flush_text_buffer() -> None:
        nonlocal text_buffer, blocks
        if not text_buffer:
            return
        current_para: List[str] = []
        for line in text_buffer:
            line = markdownize_text_line(line)
            if not line:
                if current_para:
                    blocks.append("\n".join(current_para))
                    current_para = []
                continue
            if line.startswith("- ") or re.match(r"^\d+\.\s+", line):
                if current_para:
                    blocks.append(" ".join(current_para))
                    current_para = []
                blocks.append(line)
            else:
                current_para.append(line)
        if current_para:
            blocks.append(" ".join(current_para))
        text_buffer = []

    for part in parts:
        kind = part["kind"]
        value = part["value"].strip()
        if not value:
            continue
        if kind == "text":
            text_buffer.append(value)
        else:
            flush_text_buffer()
            blocks.append(value)
    flush_text_buffer()
    return re.sub(r"\n{3,}", "\n\n", "\n\n".join(blocks)).strip()


@dataclass
class SectionNode:
    id: str
    title: str
    level: int
    page_start: int
    raw_pages: List[int] = field(default_factory=list)
    content_parts: List[Dict[str, str]] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    images: List[Dict[str, Any]] = field(default_factory=list)
    children: List["SectionNode"] = field(default_factory=list)
    section_code: str = ""
    parent_section_id: str = ""
    parent_code: str = ""
    title_path: List[str] = field(default_factory=list)

    def to_tree_dict(self) -> Dict[str, Any]:
        content = compact_markdown_parts(self.content_parts)
        return {
            "section_id": self.id,
            "section_code": self.section_code or self.id,
            "section_name": self.title,
            "title": self.title,
            "level": self.level,
            "page_start": self.page_start,
            "raw_pages": sorted(set(self.raw_pages)),
            "content": content,
            "content_preview": content[:320],
            "char_count": len(content),
            "parent_section_id": self.parent_section_id,
            "parent_code": self.parent_code,
            "title_path": list(self.title_path),
            "tables": self.tables,
            "images": self.images,
            "children_sections": [c.to_tree_dict() for c in self.children],
        }


class SectionTreeBuilder:
    def __init__(self) -> None:
        self.root = SectionNode(id="root", title="document", level=0, page_start=1)
        self.stack: List[SectionNode] = [self.root]
        self.counter = 0

    def add_heading(self, title: str, level: int, page_no: int, section_code: str = "") -> SectionNode:
        self.counter += 1
        while len(self.stack) > 1 and self.stack[-1].level >= level:
            self.stack.pop()
        parent = self.stack[-1]
        node = SectionNode(
            id=f"sec_{self.counter:04d}",
            title=title,
            level=level,
            page_start=page_no,
            raw_pages=[page_no],
            section_code=section_code or f"sec_{self.counter:04d}",
            parent_section_id=parent.id if parent.id != "root" else "",
            parent_code=parent.section_code if parent.id != "root" else "",
            title_path=[*(parent.title_path or ([] if parent.id == "root" else [parent.title])), title],
        )
        parent.children.append(node)
        self.stack.append(node)
        return node

    def current_node(self) -> SectionNode:
        return self.stack[-1]

    def to_sections(self) -> List[Dict[str, Any]]:
        return [c.to_tree_dict() for c in self.root.children]


def page_elements(page: fitz.Page, page_num: int, image_dir: Optional[Path], embed_images: bool, min_img_w: float, min_img_h: float) -> List[Dict[str, Any]]:
    lines = extract_page_lines(page)
    font_lines = extract_font_hints(page)
    table_groups = detect_table_candidates(lines)
    frames = []
    for idx, grp in enumerate(table_groups, start=1):
        frame = table_group_to_frame(grp, page_num, idx)
        if frame:
            frames.append(frame)
    elements: List[Dict[str, Any]] = []
    for line in lines:
        if line_in_any_group(line, table_groups):
            continue
        elements.append({"kind": "text", "y": line["bbox"][1], "bbox": line["bbox"], "text": line["text"], "font_size": find_font_hint_for_line(line, font_lines)})
    for frame in frames:
        elements.append({"kind": "table", "y": frame["bbox"][1], "bbox": frame["bbox"], "table": frame})
    image_blocks = get_image_blocks(page, min_img_w, min_img_h)
    for idx, block in enumerate(image_blocks, start=1):
        caption = nearby_caption(lines, block["bbox"])
        image_entry: Dict[str, Any] = {"id": f"img_p{page_num}_{idx}", "page": page_num, "bbox": block["bbox"], "width": block["width"], "height": block["height"], "caption": caption}
        pix = crop_pixmap(page, block["bbox"], zoom=2.0)
        if embed_images:
            image_entry["image_base64_png"] = image_to_base64(pix)
            md_ref = f"embedded://{image_entry['id']}"
        else:
            md_ref = f"image://p{page_num}/{idx}"
            if image_dir is not None:
                image_dir.mkdir(parents=True, exist_ok=True)
                fname = safe_filename(f"p{page_num}_{idx}.png")
                out = image_dir / fname
                pix.save(str(out))
                image_entry["image_path"] = str(out)
                md_ref = out.name
        image_entry["markdown_ref"] = md_ref
        elements.append({"kind": "image", "y": block["bbox"][1], "bbox": block["bbox"], "image": image_entry})
    elements.sort(key=lambda e: (e["y"], e["bbox"][0]))
    return elements


def _flatten_tree_sections(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    def walk(items: List[Dict[str, Any]]) -> None:
        for item in items:
            node = dict(item)
            children = list(node.pop("children_sections", []) or [])
            out.append(node)
            walk(children)

    walk(nodes)
    return out


def _leaf_sections(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    flat = _flatten_tree_sections(nodes)
    has_child = {str(item.get("parent_section_id", "")) for item in flat if str(item.get("parent_section_id", ""))}
    return [item for item in flat if str(item.get("section_id", "")) not in has_child]


def _split_text_chunks(text: str, max_chars: int = 1200, overlap: int = 120) -> List[str]:
    value = str(text or "").strip()
    if not value:
        return []
    if len(value) <= max_chars:
        return [value]
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", value) if p.strip()]
    chunks: List[str] = []
    current = ""
    for para in paragraphs:
        candidate = para if not current else f"{current}\n\n{para}"
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = (current[-overlap:].strip() + "\n\n" + para).strip() if overlap > 0 and len(current) > overlap else para
            if len(current) <= max_chars:
                continue
        while len(para) > max_chars:
            chunks.append(para[:max_chars].strip())
            para = para[max(1, max_chars - overlap):].strip()
        current = para
    if current:
        chunks.append(current)
    return [c.strip() for c in chunks if c.strip()]


def _build_review_units(sections: List[Dict[str, Any]], chunk_max_chars: int = 1200, chunk_overlap: int = 120) -> List[Dict[str, Any]]:
    units: List[Dict[str, Any]] = []
    order = 0
    for section in sections:
        section_id = str(section.get("section_id", "")).strip()
        section_code = str(section.get("section_code", "") or section_id).strip() or section_id
        section_name = str(section.get("section_name", "") or section.get("title", "") or section_code).strip() or section_code
        content = str(section.get("content", "")).strip()
        if not content:
            continue
        base_text = f"{section_code} {section_name}".strip() + "\n\n" + content
        for idx, chunk_text in enumerate(_split_text_chunks(base_text, max_chars=chunk_max_chars, overlap=chunk_overlap), start=1):
            order += 1
            units.append({
                "chunk_id": f"{section_id}_chunk_{idx}",
                "section_id": section_id,
                "section_code": section_code,
                "section_name": section_name,
                "parent_section_id": str(section.get("parent_section_id", "")).strip(),
                "parent_code": str(section.get("parent_code", "")).strip(),
                "page": section.get("page_start"),
                "page_start": section.get("page_start"),
                "page_end": max(section.get("raw_pages", []) or [section.get("page_start")]),
                "char_count": len(chunk_text),
                "text": chunk_text.strip(),
                "unit_type": "leaf_section_chunk",
                "source_section_codes": [section_code],
                "title_path": list(section.get("title_path") or []),
                "unit_order": order,
            })
    return units


def parse_submission_pdf_to_payload(file_path: str, title: Optional[str] = None, embed_images: bool = False, image_min_width: float = 100.0, image_min_height: float = 60.0, skip_toc: bool = True, merge_multiline_headings: bool = True, chunk_max_chars: int = 1200, chunk_overlap: int = 120) -> Dict[str, Any]:
    pdf_path = Path(file_path).expanduser().resolve()
    doc = fitz.open(pdf_path)
    builder = SectionTreeBuilder()
    image_dir = pdf_path.parent / f"{pdf_path.stem}_images" if not embed_images else None

    for page_index in range(len(doc)):
        page = doc[page_index]
        page_no = page_index + 1
        raw_lines = extract_page_lines(page)
        if skip_toc and is_toc_page(raw_lines):
            continue
        elements = page_elements(page, page_no, image_dir, embed_images, image_min_width, image_min_height)
        i = 0
        while i < len(elements):
            el = elements[i]
            if el["kind"] == "text":
                txt = normalize_text(el["text"])
                if not txt:
                    i += 1
                    continue
                if is_header_or_footer(txt, page.rect.height, el["bbox"]):
                    i += 1
                    continue
                merged_txt = txt
                if merge_multiline_headings and i + 1 < len(elements) and elements[i + 1]["kind"] == "text":
                    nxt_txt = normalize_text(elements[i + 1]["text"])
                    if should_merge_heading_with_next(txt, nxt_txt):
                        merged_txt = normalize_text(txt + " " + nxt_txt)
                if is_probable_heading(merged_txt, page.rect.width, el["bbox"], el.get("font_size")):
                    h = extract_heading_info(strip_trailing_colon(merged_txt))
                    if h is not None:
                        builder.add_heading(h.title, h.level, page_no, section_code=h.number or "")
                        i += 2 if merged_txt != txt else 1
                        continue
                node = builder.current_node()
                node.raw_pages.append(page_no)
                node.content_parts.append({"kind": "text", "value": txt})
                i += 1
                continue
            if el["kind"] == "table":
                node = builder.current_node()
                node.raw_pages.append(page_no)
                node.tables.append(el["table"])
                node.content_parts.append({"kind": "table", "value": el["table"]["markdown"]})
                i += 1
                continue
            if el["kind"] == "image":
                node = builder.current_node()
                img = el["image"]
                node.raw_pages.append(page_no)
                node.images.append(img)
                alt = img.get("caption", "").strip() or f"image page {img['page']}"
                node.content_parts.append({"kind": "image", "value": f"![{alt}]({img.get('markdown_ref', '')})"})
                i += 1
                continue
            i += 1

    tree_sections = builder.to_sections()
    if not tree_sections:
        fallback = SectionNode(id="sec_0001", title="全文", level=1, page_start=1, section_code="全文")
        for page_index in range(len(doc)):
            page = doc[page_index]
            page_no = page_index + 1
            raw_lines = extract_page_lines(page)
            if skip_toc and is_toc_page(raw_lines):
                continue
            elements = page_elements(page, page_no, image_dir, embed_images, image_min_width, image_min_height)
            for el in elements:
                if el["kind"] == "text":
                    txt = normalize_text(el["text"])
                    if txt and not is_header_or_footer(txt, page.rect.height, el["bbox"]):
                        fallback.raw_pages.append(page_no)
                        fallback.content_parts.append({"kind": "text", "value": txt})
                elif el["kind"] == "table":
                    fallback.raw_pages.append(page_no)
                    fallback.tables.append(el["table"])
                    fallback.content_parts.append({"kind": "table", "value": el["table"]["markdown"]})
                elif el["kind"] == "image":
                    img = el["image"]
                    fallback.raw_pages.append(page_no)
                    fallback.images.append(img)
                    alt = img.get("caption", "").strip() or f"image page {img['page']}"
                    fallback.content_parts.append({"kind": "image", "value": f"![{alt}]({img.get('markdown_ref', '')})"})
        tree_sections = [fallback.to_tree_dict()]

    flat_sections = _flatten_tree_sections(tree_sections)
    leaf_sections = _leaf_sections(tree_sections)
    review_units = _build_review_units(leaf_sections, chunk_max_chars=chunk_max_chars, chunk_overlap=chunk_overlap)
    return {
        "schema_version": "submission_pdf_markdown_v1",
        "title": title or pdf_path.stem,
        "source_pdf": str(pdf_path),
        "structure_type": "generic_heading_based_markdown_json_v2",
        "parser": {
            "heading_strategy": "regex_heading_detection_with_layout_and_font_filters",
            "chunking_strategy": "leaf_section_markdown_chunking",
            "skip_toc": skip_toc,
            "merge_multiline_headings": merge_multiline_headings,
            "embed_images": embed_images,
            "chunk_max_chars": chunk_max_chars,
            "chunk_overlap": chunk_overlap,
        },
        "sections": flat_sections,
        "section_tree": tree_sections,
        "chapter_structure": tree_sections,
        "leaf_sibling_groups": [],
        "review_units": review_units,
        "statistics": {"section_count": len(flat_sections), "leaf_section_count": len(leaf_sections), "review_unit_count": len(review_units), "page_count": len(doc)},
    }


def derive_default_output(pdf_path: Path) -> Path:
    return pdf_path.parent / f"{pdf_path.stem}_parsed_markdown.json"


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="通用 PDF -> 章节 Markdown JSON")
    parser.add_argument("pdf", help="输入 PDF 文件路径")
    parser.add_argument("--output-json", help="输出 JSON 路径")
    parser.add_argument("--title", default=None, help="文档标题")
    parser.add_argument("--embed-images", default="false", help="是否将图片以 base64 内嵌到 JSON：true/false")
    parser.add_argument("--image-min-width", type=float, default=100.0, help="识别图片块最小宽度")
    parser.add_argument("--image-min-height", type=float, default=60.0, help="识别图片块最小高度")
    parser.add_argument("--skip-toc", default="true", help="是否跳过目录页：true/false")
    parser.add_argument("--merge-multiline-headings", default="true", help="是否合并跨行标题：true/false")
    args = parser.parse_args()

    pdf_path = Path(args.pdf).expanduser().resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")
    output_json = Path(args.output_json).expanduser().resolve() if args.output_json else derive_default_output(pdf_path)
    result = parse_submission_pdf_to_payload(file_path=str(pdf_path), title=args.title, embed_images=str2bool(args.embed_images), image_min_width=args.image_min_width, image_min_height=args.image_min_height, skip_toc=str2bool(args.skip_toc), merge_multiline_headings=str2bool(args.merge_multiline_headings))
    output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] JSON: {output_json}")


if __name__ == "__main__":
    main()
