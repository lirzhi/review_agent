import os
import re
from typing import Dict, List

from agent.agent_backend.utils.parser.docx_parser import parse_docx


def _chunk_lines(lines: List[str], max_len: int = 800) -> List[str]:
    print(f"[ParserDebug] _chunk_lines called: line_count={len(lines)}, max_len={max_len}")
    chunks: List[str] = []
    current = ""
    for line in lines:
        clean = str(line or "").strip()
        if not clean:
            continue
        if len(current) + len(clean) + 1 <= max_len:
            current = f"{current}\n{clean}".strip()
        else:
            if current:
                chunks.append(current)
            current = clean
    if current:
        chunks.append(current)
    print(f"[ParserDebug] _chunk_lines result: chunk_count={len(chunks)}")
    return chunks


def _looks_like_docx(file_path: str) -> bool:
    try:
        with open(file_path, "rb") as f:
            head = f.read(4)
        is_docx = head == b"PK\x03\x04"
        print(f"[ParserDebug] _looks_like_docx: file_path={file_path}, is_docx={is_docx}")
        return is_docx
    except Exception as exc:
        print(f"[ParserDebug] _looks_like_docx failed: file_path={file_path}, error={exc}")
        return False


def _extract_utf16_text(raw: bytes) -> List[str]:
    # Old .doc often stores text in UTF-16LE-like runs.
    pattern = re.compile(rb"(?:[\x20-\x7e]\x00|[\x80-\xff][\x00-\xff]){8,}")
    lines: List[str] = []
    for match in pattern.finditer(raw):
        blob = match.group(0)
        try:
            text = blob.decode("utf-16le", errors="ignore")
        except Exception:
            continue
        for line in re.split(r"[\r\n\t]+", text):
            line = re.sub(r"\s+", " ", line).strip()
            if len(line) >= 4:
                lines.append(line)
    print(f"[ParserDebug] _extract_utf16_text result: line_count={len(lines)}")
    return lines


def _extract_single_byte_text(raw: bytes) -> List[str]:
    # Fallback for compressed old-doc text and mixed encodings.
    pattern = re.compile(rb"[\x20-\x7e\x80-\xff]{12,}")
    lines: List[str] = []
    for match in pattern.finditer(raw):
        blob = match.group(0)
        decoded = ""
        for enc in ("gb18030", "gbk", "utf-8", "latin1"):
            try:
                decoded = blob.decode(enc, errors="ignore")
                if decoded:
                    break
            except Exception:
                continue
        if not decoded:
            continue
        for line in re.split(r"[\r\n\t]+", decoded):
            line = re.sub(r"\s+", " ", line).strip()
            if len(line) >= 4:
                lines.append(line)
    print(f"[ParserDebug] _extract_single_byte_text result: line_count={len(lines)}")
    return lines


def _dedupe_lines(lines: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for line in lines:
        normalized = re.sub(r"\s+", " ", str(line or "")).strip()
        if not normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    print(f"[ParserDebug] _dedupe_lines result: before={len(lines)}, after={len(result)}")
    return result


def parse_doc(file_path: str) -> List[Dict]:
    print(f"[ParserDebug] parse_doc called: file_path={file_path}")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"file not found: {file_path}")

    if _looks_like_docx(file_path):
        print(f"[ParserDebug] parse_doc fallback_to_docx: file_path={file_path}")
        return parse_docx(file_path)

    with open(file_path, "rb") as f:
        raw = f.read()
    print(f"[ParserDebug] parse_doc read: byte_len={len(raw)}")

    utf16_lines = _extract_utf16_text(raw)
    single_byte_lines = _extract_single_byte_text(raw)
    merged_lines = _dedupe_lines(utf16_lines + single_byte_lines)
    chunks = _chunk_lines(merged_lines)

    result: List[Dict] = []
    for idx, chunk in enumerate(chunks, start=1):
        result.append(
            {
                "chunk_id": f"doc_{idx}",
                "page": None,
                "text": chunk,
                "tables": [],
                "image_paths": [],
            }
        )
    print(
        f"[ParserDebug] parse_doc success: utf16_lines={len(utf16_lines)}, "
        f"single_byte_lines={len(single_byte_lines)}, chunk_count={len(result)}"
    )
    return result
