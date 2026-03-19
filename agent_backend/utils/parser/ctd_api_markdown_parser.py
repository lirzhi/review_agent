import base64
import copy
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import fitz
import numpy as np
import pytesseract


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n\s+", "\n", text)
    return text.strip()


def _escape_md(text: str) -> str:
    return str(text).replace("\n", " ").strip().replace("|", "\\|")


def _markdown_table(columns: List[str], data: List[List[str]]) -> str:
    if not columns:
        return ""
    rows = []
    rows.append("| " + " | ".join(_escape_md(col) for col in columns) + " |")
    rows.append("| " + " | ".join("---" for _ in columns) + " |")
    for row in data:
        normalized = row + [""] * (len(columns) - len(row))
        rows.append("| " + " | ".join(_escape_md(col) for col in normalized[: len(columns)]) + " |")
    return "\n".join(rows)


def _markdownize_text_line(text: str) -> str:
    value = _normalize_text(text)
    if not value:
        return ""
    match = re.match(r"^\s*([（(]?\d+[）)])\s*(.+)$", value)
    if match:
        return f"1. {match.group(2).strip()}"
    match = re.match(r"^\s*([一二三四五六七八九十]+[、.])\s*(.+)$", value)
    if match:
        return f"- {match.group(2).strip()}"
    match = re.match(r"^\s*([\-•·●])\s*(.+)$", value)
    if match:
        return f"- {match.group(2).strip()}"
    return value


def _branch_outline_from_catalog(catalog: Dict[str, Any], root_section_id: str) -> List[Dict[str, Any]]:
    roots = catalog.get("chapter_structure", []) if isinstance(catalog, dict) else []
    for node in roots:
        if not isinstance(node, dict):
            continue
        if str(node.get("section_id", "")).strip() == str(root_section_id or "").strip():
            return copy.deepcopy(node.get("children_sections") or [])
    return []


def _flatten_sections(outline: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    sections: List[Dict[str, str]] = []

    def walk(items: List[Dict[str, Any]]) -> None:
        for item in items:
            sections.append(
                {
                    "section_id": str(item.get("section_id", "")).strip(),
                    "section_name": str(item.get("section_name", "")).strip(),
                }
            )
            walk(item.get("children_sections") or [])

    walk(outline)
    sections = [item for item in sections if item["section_id"]]
    sections.sort(key=lambda item: len(item["section_id"]), reverse=True)
    return sections


def _init_outline(outline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    tree = copy.deepcopy(outline)

    def walk(items: List[Dict[str, Any]]) -> None:
        for item in items:
            item.setdefault("content", "")
            item.setdefault("tables", [])
            item.setdefault("raw_pages", [])
            item.setdefault("_content_parts", [])
            walk(item.get("children_sections") or [])

    walk(tree)
    return tree


def _clean_internal_fields(items: List[Dict[str, Any]]) -> None:
    for item in items:
        item.pop("_content_parts", None)
        _clean_internal_fields(item.get("children_sections") or [])


def _find_section_node(items: List[Dict[str, Any]], section_id: str) -> Optional[Dict[str, Any]]:
    for item in items:
        if str(item.get("section_id", "")).strip() == section_id:
            return item
        found = _find_section_node(item.get("children_sections") or [], section_id)
        if found:
            return found
    return None


def _append_unique_page(node: Dict[str, Any], page_no: int) -> None:
    pages = node.setdefault("raw_pages", [])
    if page_no not in pages:
        pages.append(page_no)


def _build_heading_patterns(section_id: str, section_name: str) -> List[re.Pattern]:
    escaped_id = re.escape(section_id)
    escaped_name = re.escape(section_name)
    return [
        re.compile(rf"^\s*{escaped_id}\s*[\.、]?\s*{escaped_name}\s*$"),
        re.compile(rf"^\s*{escaped_id}\s+[^\n]*{escaped_name}\s*$"),
        re.compile(rf"^\s*{escaped_id}\s*$"),
        re.compile(rf"^\s*{escaped_name}\s*$"),
    ]


def _match_heading(line: str, sections: List[Dict[str, str]]) -> Tuple[str, str]:
    text = _normalize_text(line)
    for section in sections:
        for pattern in _build_heading_patterns(section["section_id"], section["section_name"]):
            if pattern.match(text):
                return section["section_id"], section["section_name"]
    match = re.match(r"^\s*(3\.2\.S\.\d+(?:\.\d+)*)\b", text)
    if match:
        return match.group(1), ""
    return "", ""


def _merge_wrapped_lines(lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not lines:
        return []
    merged = [lines[0]]
    for current in lines[1:]:
        previous = merged[-1]
        gap = current["bbox"][1] - previous["bbox"][3]
        same_block = gap < 5
        previous_text = previous["text"]
        current_text = current["text"]
        should_merge = (
            same_block
            and previous_text
            and current_text
            and not re.match(r"^\s*3\.2\.S\.", current_text)
            and not previous_text.endswith(("。", "；", "：", ":", ".", "）", ")", "|"))
        )
        if should_merge:
            previous["text"] = _normalize_text(previous["text"] + " " + current["text"])
            previous["bbox"] = [
                min(previous["bbox"][0], current["bbox"][0]),
                min(previous["bbox"][1], current["bbox"][1]),
                max(previous["bbox"][2], current["bbox"][2]),
                max(previous["bbox"][3], current["bbox"][3]),
            ]
            previous["words"].extend(current["words"])
            continue
        merged.append(current)
    return merged


def _extract_page_lines(page: fitz.Page) -> List[Dict[str, Any]]:
    words = page.get_text("words")
    if not words:
        return []
    rows: Dict[float, List[Any]] = {}
    for word in words:
        x0, y0, x1, y1, text, *_ = word
        rows.setdefault(round(y0, 1), []).append((x0, y0, x1, y1, text))

    line_objs: List[Dict[str, Any]] = []
    for key in sorted(rows.keys()):
        row_words = sorted(rows[key], key=lambda item: item[0])
        line_objs.append(
            {
                "type": "line",
                "text": _normalize_text(" ".join(word[4] for word in row_words)),
                "bbox": [
                    min(word[0] for word in row_words),
                    min(word[1] for word in row_words),
                    max(word[2] for word in row_words),
                    max(word[3] for word in row_words),
                ],
                "words": row_words,
            }
        )
    return _merge_wrapped_lines(line_objs)


def _detect_table_candidates(lines: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    groups: List[List[Dict[str, Any]]] = []
    current: List[Dict[str, Any]] = []

    def is_tableish(text: str) -> bool:
        score = 0
        score += text.count("|")
        score += len(re.findall(r"\s{2,}", text))
        if re.search(r"(批号|项目|结果|标准|限度|方法|时间|条件|样品|杂质|含量|峰号|保留时间|平均值|相对偏差)", text):
            score += 2
        if re.search(r"^\s*[\w\u4e00-\u9fa5\-\+\(\)（）/%\.]+\s+[\w\u4e00-\u9fa5\-\+\(\)（）/%\.]+\s+[\w\u4e00-\u9fa5\-\+\(\)（）/%\.]+", text):
            score += 1
        return score >= 2

    for line in lines:
        if is_tableish(line["text"]):
            current.append(line)
            continue
        if len(current) >= 2:
            groups.append(current)
        current = []
    if len(current) >= 2:
        groups.append(current)
    return groups


def _split_columns_from_words(line: Dict[str, Any], gap_threshold: float = 18.0) -> List[str]:
    words = sorted(line["words"], key=lambda item: item[0])
    if not words:
        return []
    cells: List[List[str]] = [[words[0][4]]]
    previous_x1 = words[0][2]
    for word in words[1:]:
        if word[0] - previous_x1 > gap_threshold:
            cells.append([word[4]])
        else:
            cells[-1].append(word[4])
        previous_x1 = word[2]
    return [_normalize_text(" ".join(cell)) for cell in cells if _normalize_text(" ".join(cell))]


def _group_bbox(group: List[Dict[str, Any]]) -> List[float]:
    return [
        min(item["bbox"][0] for item in group),
        min(item["bbox"][1] for item in group),
        max(item["bbox"][2] for item in group),
        max(item["bbox"][3] for item in group),
    ]


def _table_group_to_frame(group: List[Dict[str, Any]], page_num: int, table_idx: int) -> Dict[str, Any]:
    rows = [_split_columns_from_words(line) for line in group]
    rows = [row for row in rows if row]
    if not rows:
        return {}
    max_cols = max(len(row) for row in rows)
    normalized_rows = [row + [""] * (max_cols - len(row)) for row in rows]
    columns = normalized_rows[0]
    data = normalized_rows[1:] if len(normalized_rows) > 1 else []
    return {
        "id": f"tbl_p{page_num}_{table_idx}",
        "type": "frame",
        "source": "text",
        "page": page_num,
        "bbox": _group_bbox(group),
        "columns": columns,
        "data": data,
        "markdown": _markdown_table(columns, data),
    }


def _image_to_base64(pix: fitz.Pixmap) -> str:
    return base64.b64encode(pix.tobytes("png")).decode("utf-8")


def _get_image_blocks(page: fitz.Page, min_width: float, min_height: float) -> List[Dict[str, Any]]:
    info = page.get_text("dict")
    blocks = info.get("blocks", [])
    result: List[Dict[str, Any]] = []
    index = 0
    for block in blocks:
        if block.get("type") != 1:
            continue
        bbox = block.get("bbox")
        if not bbox:
            continue
        x0, y0, x1, y1 = bbox
        width = x1 - x0
        height = y1 - y0
        if width < min_width or height < min_height:
            continue
        index += 1
        result.append(
            {
                "type": "image_block",
                "bbox": [x0, y0, x1, y1],
                "width": width,
                "height": height,
                "index": index,
            }
        )
    return result


def _nearby_caption(lines: List[Dict[str, Any]], bbox: List[float], max_gap: float = 28.0) -> str:
    x0, y0, x1, y1 = bbox
    captions: List[str] = []
    for line in lines:
        lx0, ly0, lx1, ly1 = line["bbox"]
        vertical_near = (0 <= ly0 - y1 <= max_gap) or (0 <= y0 - ly1 <= max_gap)
        horizontal_overlap = not (lx1 < x0 or lx0 > x1)
        if vertical_near and horizontal_overlap and re.search(r"(表|图|Table|Figure|\d)", line["text"]):
            captions.append(line["text"])
    return _normalize_text(" ".join(captions))


def _crop_pixmap(page: fitz.Page, bbox: List[float], zoom: float = 2.5) -> fitz.Pixmap:
    return page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=fitz.Rect(bbox), alpha=False)


def _pixmap_to_cv(pix: fitz.Pixmap) -> np.ndarray:
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        return cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
    if pix.n == 3:
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    return cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)


def _preprocess_table_image(img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    return cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 11)


def _detect_grid_cells(bin_img: np.ndarray) -> List[Tuple[int, int, int, int]]:
    height, width = bin_img.shape
    scale_x = max(20, width // 25)
    scale_y = max(20, height // 25)
    horiz_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (scale_x, 1))
    vert_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, scale_y))
    horiz = cv2.morphologyEx(bin_img, cv2.MORPH_OPEN, horiz_kernel)
    vert = cv2.morphologyEx(bin_img, cv2.MORPH_OPEN, vert_kernel)
    grid = cv2.add(horiz, vert)
    grid = cv2.dilate(grid, np.ones((3, 3), np.uint8), iterations=1)
    contours, _ = cv2.findContours(grid, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    cells: List[Tuple[int, int, int, int]] = []
    for contour in contours:
        x, y, cell_w, cell_h = cv2.boundingRect(contour)
        area = cell_w * cell_h
        if cell_w < 20 or cell_h < 12 or area < 500:
            continue
        if cell_w > 0.98 * width and cell_h > 0.98 * height:
            continue
        cells.append((x, y, cell_w, cell_h))
    deduped: List[Tuple[int, int, int, int]] = []
    for cell in sorted(cells, key=lambda item: (item[1], item[0], item[2] * item[3])):
        keep = True
        for existing in deduped:
            if (
                abs(cell[0] - existing[0]) < 6
                and abs(cell[1] - existing[1]) < 6
                and abs(cell[2] - existing[2]) < 8
                and abs(cell[3] - existing[3]) < 8
            ):
                keep = False
                break
        if keep:
            deduped.append(cell)
    return deduped


def _cluster_positions(values: List[float], tol: float = 12.0) -> List[float]:
    if not values:
        return []
    ordered = sorted(values)
    groups = [[ordered[0]]]
    for value in ordered[1:]:
        if abs(value - groups[-1][-1]) <= tol:
            groups[-1].append(value)
        else:
            groups.append([value])
    return [sum(group) / len(group) for group in groups]


def _assign_to_cluster(value: float, centers: List[float]) -> int:
    distances = [abs(value - center) for center in centers]
    return int(np.argmin(distances))


def _ocr_cell(img: np.ndarray, lang: str) -> str:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.copyMakeBorder(gray, 6, 6, 6, 6, cv2.BORDER_CONSTANT, value=255)
    threshold = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    text = pytesseract.image_to_string(threshold, lang=lang, config="--oem 1 --psm 6")
    return _normalize_text(re.sub(r"\s{2,}", " ", text))


def _ocr_table_from_image(img: np.ndarray, lang: str) -> Optional[Dict[str, Any]]:
    bin_img = _preprocess_table_image(img)
    cells = _detect_grid_cells(bin_img)
    if len(cells) < 4:
        return None
    row_centers = _cluster_positions([y + h / 2 for (_, y, _, h) in cells], tol=18.0)
    col_centers = _cluster_positions([x + w / 2 for (x, _, w, _) in cells], tol=24.0)
    if len(row_centers) < 2 or len(col_centers) < 2:
        return None
    grid: Dict[Tuple[int, int], str] = {}
    for x, y, width, height in cells:
        row_index = _assign_to_cluster(y + height / 2, row_centers)
        col_index = _assign_to_cluster(x + width / 2, col_centers)
        pad_x = max(2, int(width * 0.04))
        pad_y = max(2, int(height * 0.08))
        x0 = max(0, x + pad_x)
        y0 = max(0, y + pad_y)
        x1 = min(img.shape[1], x + width - pad_x)
        y1 = min(img.shape[0], y + height - pad_y)
        cell_text = ""
        if x1 > x0 and y1 > y0:
            cell_text = _ocr_cell(img[y0:y1, x0:x1], lang=lang)
        grid[(row_index, col_index)] = cell_text
    rows: List[List[str]] = []
    for row_index in range(len(row_centers)):
        row = []
        for col_index in range(len(col_centers)):
            row.append(_normalize_text(grid.get((row_index, col_index), "")))
        rows.append(row)
    rows = [row for row in rows if any(_normalize_text(cell) for cell in row)]
    if len(rows) < 2:
        return None
    keep_cols: List[int] = []
    max_cols = max(len(row) for row in rows)
    for col_index in range(max_cols):
        if any(col_index < len(row) and _normalize_text(row[col_index]) for row in rows):
            keep_cols.append(col_index)
    rows = [[row[col_index] if col_index < len(row) else "" for col_index in keep_cols] for row in rows]
    if len(rows) < 2 or len(rows[0]) < 2:
        return None
    fill_ratio = sum(1 for row in rows for cell in row if _normalize_text(cell)) / max(1, len(rows) * len(rows[0]))
    if fill_ratio < 0.18:
        return None
    columns = rows[0]
    data = rows[1:]
    if sum(1 for cell in columns if _normalize_text(cell)) <= max(1, len(columns) // 3):
        columns = [f"col_{idx + 1}" for idx in range(len(columns))]
        data = rows
    return {"columns": columns, "data": data}


def _bbox_overlap(b1: List[float], b2: List[float]) -> bool:
    return not (b1[2] < b2[0] or b1[0] > b2[2] or b1[3] < b2[1] or b1[1] > b2[3])


def _line_in_any_group(line: Dict[str, Any], groups: List[List[Dict[str, Any]]]) -> bool:
    for group in groups:
        if _bbox_overlap(line["bbox"], _group_bbox(group)):
            return True
    return False


def _image_block_to_entry(
    page: fitz.Page,
    lines: List[Dict[str, Any]],
    block: Dict[str, Any],
    page_num: int,
    image_idx: int,
    embed_images: bool,
    ocr_lang: str,
) -> Dict[str, Any]:
    caption = _nearby_caption(lines, block["bbox"])
    pix = _crop_pixmap(page, block["bbox"], zoom=2.5)
    cv_img = _pixmap_to_cv(pix)
    ocr_table = _ocr_table_from_image(cv_img, lang=ocr_lang)
    if ocr_table is not None:
        entry = {
            "id": f"imgtbl_p{page_num}_{image_idx}",
            "type": "frame",
            "source": "image_ocr",
            "page": page_num,
            "bbox": block["bbox"],
            "width": block["width"],
            "height": block["height"],
            "caption": caption,
            "columns": ocr_table["columns"],
            "data": ocr_table["data"],
        }
        entry["markdown"] = _markdown_table(entry["columns"], entry["data"])
        if embed_images:
            entry["image_base64_png"] = _image_to_base64(pix)
        return entry
    entry = {
        "id": f"imgtbl_p{page_num}_{image_idx}",
        "type": "image_frame",
        "source": "image_fallback",
        "page": page_num,
        "bbox": block["bbox"],
        "width": block["width"],
        "height": block["height"],
        "caption": caption,
        "markdown_ref": f"table_image://p{page_num}/{image_idx}",
    }
    if embed_images:
        entry["image_base64_png"] = _image_to_base64(pix)
    return entry


def _page_elements(
    page: fitz.Page,
    page_num: int,
    min_img_w: float,
    min_img_h: float,
    embed_images: bool,
    ocr_lang: str,
) -> List[Dict[str, Any]]:
    lines = _extract_page_lines(page)
    table_groups = _detect_table_candidates(lines)
    frames = []
    for index, group in enumerate(table_groups, start=1):
        frame = _table_group_to_frame(group, page_num, index)
        if frame:
            frames.append(frame)
    image_blocks = _get_image_blocks(page, min_img_w, min_img_h)
    image_entries = [
        _image_block_to_entry(page, lines, block, page_num, index, embed_images, ocr_lang)
        for index, block in enumerate(image_blocks, start=1)
    ]
    elements: List[Dict[str, Any]] = []
    for line in lines:
        if _line_in_any_group(line, table_groups):
            continue
        elements.append({"kind": "text", "y": line["bbox"][1], "bbox": line["bbox"], "text": line["text"]})
    for frame in frames:
        elements.append({"kind": "frame", "y": frame["bbox"][1], "bbox": frame["bbox"], "frame": frame})
    for image in image_entries:
        elements.append({"kind": "image", "y": image["bbox"][1], "bbox": image["bbox"], "image": image})
    elements.sort(key=lambda item: (item["y"], item["bbox"][0]))
    return elements


def _compact_markdown_parts(parts: List[Dict[str, str]]) -> str:
    blocks: List[str] = []
    text_buffer: List[str] = []

    def flush_text_buffer() -> None:
        nonlocal text_buffer
        if not text_buffer:
            return
        current_paragraph: List[str] = []
        for line in text_buffer:
            normalized = _markdownize_text_line(line)
            if not normalized:
                if current_paragraph:
                    blocks.append("\n".join(current_paragraph))
                    current_paragraph = []
                continue
            if normalized.startswith("- ") or re.match(r"^\d+\.\s+", normalized):
                if current_paragraph:
                    blocks.append(" ".join(current_paragraph))
                    current_paragraph = []
                blocks.append(normalized)
            else:
                current_paragraph.append(normalized)
        if current_paragraph:
            blocks.append(" ".join(current_paragraph))
        text_buffer = []

    for part in parts:
        kind = part["kind"]
        value = part["value"].strip()
        if not value:
            continue
        if kind == "text":
            text_buffer.append(value)
            continue
        flush_text_buffer()
        blocks.append(value)

    flush_text_buffer()
    text = "\n\n".join(blocks)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _finalize_tree(nodes: List[Dict[str, Any]]) -> None:
    for item in nodes:
        item["content"] = _compact_markdown_parts(item.get("_content_parts") or [])
        _finalize_tree(item.get("children_sections") or [])


def _collect_sections(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for node in nodes or []:
        section_id = str(node.get("section_id", "")).strip()
        if section_id:
            out.append(
                {
                    "section_id": section_id,
                    "section_code": str(node.get("section_code", section_id)).strip() or section_id,
                    "section_name": str(node.get("section_name", section_id)).strip() or section_id,
                    "title": str(node.get("section_name", section_id)).strip() or section_id,
                    "content": str(node.get("content", "")).strip(),
                    "content_preview": str(node.get("content", "")).strip()[:320],
                    "char_count": len(str(node.get("content", "")).strip()),
                    "page_start": min(node.get("raw_pages") or []) if node.get("raw_pages") else None,
                    "page_end": max(node.get("raw_pages") or []) if node.get("raw_pages") else None,
                    "raw_pages": list(node.get("raw_pages") or []),
                    "tables": list(node.get("tables") or []),
                    "title_path": list(node.get("title_path") or []),
                    "parent_section_id": str(node.get("parent_section_id", "")).strip(),
                }
            )
        out.extend(_collect_sections(node.get("children_sections") or []))
    return out


def parse_ctd_api_pdf_to_payload(
    file_path: str,
    catalog: Dict[str, Any],
    root_section_id: str = "3.2.S",
    title: str = "CTD 解析结果",
    embed_images: bool = False,
    image_min_width: float = 120.0,
    image_min_height: float = 60.0,
    ocr_lang: str = "chi_sim+eng",
) -> Dict[str, Any]:
    outline = _branch_outline_from_catalog(catalog, root_section_id)
    if not outline:
        return {
            "title": title,
            "source_pdf": str(file_path),
            "root_section_id": root_section_id,
            "structure_type": "ctd_api_markdown_json",
            "chapter_structure": [],
            "sections": [],
            "review_units": [],
            "leaf_sibling_groups": [],
            "statistics": {"matched_section_total": 0},
        }

    tree = _init_outline(outline)
    flat_sections = _flatten_sections(outline)
    current_section_id = ""
    doc = fitz.open(Path(file_path))
    try:
        for page_index in range(len(doc)):
            page = doc[page_index]
            page_no = page_index + 1
            elements = _page_elements(page, page_no, image_min_width, image_min_height, embed_images, ocr_lang)
            for element in elements:
                if element["kind"] == "text":
                    section_id, _ = _match_heading(element["text"], flat_sections)
                    if section_id:
                        current_section_id = section_id
                        node = _find_section_node(tree, section_id)
                        if node:
                            _append_unique_page(node, page_no)
                        continue
                    if current_section_id:
                        node = _find_section_node(tree, current_section_id)
                        if node:
                            _append_unique_page(node, page_no)
                            node.setdefault("_content_parts", []).append({"kind": "text", "value": element["text"]})
                elif element["kind"] == "frame" and current_section_id:
                    node = _find_section_node(tree, current_section_id)
                    if node:
                        _append_unique_page(node, page_no)
                        node.setdefault("tables", []).append(element["frame"])
                        node.setdefault("_content_parts", []).append({"kind": "table", "value": element["frame"]["markdown"]})
                elif element["kind"] == "image" and current_section_id:
                    node = _find_section_node(tree, current_section_id)
                    if node:
                        _append_unique_page(node, page_no)
                        node.setdefault("tables", []).append(element["image"])
                        if element["image"]["type"] == "frame":
                            node.setdefault("_content_parts", []).append({"kind": "table", "value": element["image"]["markdown"]})
                        else:
                            caption = element["image"].get("caption", "").strip() or f"图片表格 page {element['image']['page']}"
                            node.setdefault("_content_parts", []).append(
                                {
                                    "kind": "image",
                                    "value": f"![{caption}]({element['image']['markdown_ref']})",
                                }
                            )
    finally:
        doc.close()

    _finalize_tree(tree)
    sections = _collect_sections(tree)
    _clean_internal_fields(tree)
    review_units: List[Dict[str, Any]] = []
    for section in sections:
        text = str(section.get("content", "")).strip()
        if not text:
            continue
        section_id = str(section.get("section_id", "")).strip()
        review_units.append(
            {
                "chunk_id": section_id,
                "section_id": section_id,
                "section_code": str(section.get("section_code", section_id)).strip() or section_id,
                "section_name": str(section.get("section_name", section_id)).strip() or section_id,
                "page": section.get("page_start"),
                "page_start": section.get("page_start"),
                "page_end": section.get("page_end"),
                "text": text,
                "title_path": list(section.get("title_path") or []),
                "parent_section_id": str(section.get("parent_section_id", "")).strip(),
                "pipeline": "ctd_api_markdown_parser",
            }
        )

    return {
        "title": title,
        "source_pdf": str(file_path),
        "root_section_id": root_section_id,
        "structure_type": "ctd_api_markdown_json",
        "chapter_structure": tree,
        "sections": sections,
        "review_units": review_units,
        "leaf_sibling_groups": [],
        "statistics": {"matched_section_total": len(review_units)},
    }
