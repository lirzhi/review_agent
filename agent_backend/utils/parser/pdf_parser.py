from typing import Dict, List

import fitz


def _chunk_text(text: str, max_len: int = 800) -> List[str]:
    print("[DEBUG] enter _chunk_text | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    print(f"[ParserDebug] _chunk_text called: text_len={len(text or '')}, max_len={max_len}")
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    chunks: List[str] = []
    cur = ""
    for line in lines:
        if len(cur) + len(line) + 1 <= max_len:
            cur = f"{cur} {line}".strip()
        else:
            if cur:
                chunks.append(cur)
            cur = line
    if cur:
        chunks.append(cur)
    print(f"[ParserDebug] _chunk_text result: line_count={len(lines)}, chunk_count={len(chunks)}")
    return chunks


def parse_pdf(file_path: str) -> List[Dict]:
    print("[DEBUG] enter parse_pdf | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
    print(f"[ParserDebug] parse_pdf called: file_path={file_path}")
    result: List[Dict] = []
    with fitz.open(file_path) as doc:
        print(f"[ParserDebug] parse_pdf opened: page_count={len(doc)}")
        for page_idx, page in enumerate(doc, start=1):
            page_text = page.get_text("text") or ""
            page_chunks = _chunk_text(page_text)
            print(
                f"[ParserDebug] parse_pdf page processed: page={page_idx}, "
                f"text_len={len(page_text)}, chunk_count={len(page_chunks)}"
            )
            for i, chunk in enumerate(page_chunks, start=1):
                result.append(
                    {
                        "chunk_id": f"p{page_idx}_{i}",
                        "page": page_idx,
                        "text": chunk,
                        "tables": [],
                        "image_paths": [],
                    }
                )
    print(f"[ParserDebug] parse_pdf success: total_chunks={len(result)}")
    return result
