from typing import List, Dict


def parse_material(file_path: str) -> List[Dict]:
    print("[方法调试] 进入 parse_material | 局部变量:", locals())
    print(f"[ParserDebug] parse_material called: file_path={file_path}")
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    print(f"[ParserDebug] parse_material read: text_len={len(text)}")
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    chunks = [{"chunk_id": f"m_{i+1}", "page": None, "text": line} for i, line in enumerate(lines)]
    print(f"[ParserDebug] parse_material success: line_count={len(lines)}, chunk_count={len(chunks)}")
    return chunks
