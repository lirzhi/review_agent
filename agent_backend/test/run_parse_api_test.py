import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests


SUPPORTED_EXTS = {".pdf", ".doc", ".docx", ".txt", ".md"}


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def build_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def post_json(base_url: str, path: str, payload: Optional[Dict[str, Any]] = None, timeout: int = 60) -> Dict[str, Any]:
    url = build_url(base_url, path)
    resp = requests.post(url, json=(payload or {}), timeout=timeout)
    try:
        return {"status_code": resp.status_code, "data": resp.json()}
    except Exception:
        return {"status_code": resp.status_code, "data": {"code": resp.status_code, "message": resp.text}}


def upload_file(base_url: str, file_path: Path, classification: str = "指导原则", timeout: int = 120) -> Dict[str, Any]:
    url = build_url(base_url, "/knowledge/upload")
    with file_path.open("rb") as fp:
        files = {"file": (file_path.name, fp)}
        data = {"classification": classification, "affect_range": "other"}
        resp = requests.post(url, files=files, data=data, timeout=timeout)
    try:
        body = resp.json()
    except Exception:
        body = {"code": resp.status_code, "message": resp.text}
    return {"status_code": resp.status_code, "data": body}


def submit_parse(base_url: str, doc_id: str) -> Dict[str, Any]:
    return post_json(base_url, f"/knowledge/{doc_id}/parse", {})


def get_progress(base_url: str, doc_id: str) -> Tuple[str, float, str, Dict[str, Any]]:
    result = post_json(base_url, "/knowledge/parse-progress", {"doc_id": doc_id})
    body = result.get("data", {})
    tasks = ((body.get("data") or {}).get("tasks") or []) if isinstance(body, dict) else []
    if not tasks:
        return "unknown", 0.0, "", result
    task = tasks[0] if isinstance(tasks[0], dict) else {}
    status = str(task.get("status", "unknown"))
    progress = float(task.get("progress", 0.0) or 0.0)
    message = str(task.get("message", "") or "")
    return status, progress, message, result


def get_file_detail(base_url: str, doc_id: str) -> Dict[str, Any]:
    return post_json(base_url, f"/files/{doc_id}/detail", {})


def load_local_chunks(project_root: Path, doc_id: str) -> List[Dict[str, Any]]:
    parsed_path = project_root / "agent" / "agent_backend" / "data" / "parsed" / f"{doc_id}.json"
    if not parsed_path.exists():
        return []
    try:
        with parsed_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def preview_chunks(chunks: List[Dict[str, Any]], limit: int = 3) -> List[Dict[str, Any]]:
    previews: List[Dict[str, Any]] = []
    for item in chunks[:limit]:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "") or "")
        previews.append(
            {
                "chunk_id": item.get("chunk_id"),
                "section_id": item.get("section_id"),
                "page": item.get("page"),
                "text_preview": text[:200],
                "summary": str(item.get("summary", "") or "")[:200],
            }
        )
    return previews


def run_one_file(base_url: str, project_root: Path, file_path: Path, out_dir: Path, poll_seconds: int, timeout_seconds: int) -> Dict[str, Any]:
    print(f"[{now_str()}] 开始测试文件: {file_path.name}")
    result: Dict[str, Any] = {
        "file_name": file_path.name,
        "file_path": str(file_path),
        "started_at": now_str(),
    }

    upload_ret = upload_file(base_url, file_path)
    result["upload_response"] = upload_ret
    body = upload_ret.get("data", {})
    data = body.get("data", {}) if isinstance(body, dict) else {}
    doc_id = str((data or {}).get("doc_id", "") or "")
    if not doc_id:
        result["ok"] = False
        result["error"] = f"上传失败或未返回 doc_id: {body}"
        result["ended_at"] = now_str()
        return result
    result["doc_id"] = doc_id
    print(f"[{now_str()}] 上传成功，doc_id={doc_id}")

    parse_ret = submit_parse(base_url, doc_id)
    result["parse_submit_response"] = parse_ret
    print(f"[{now_str()}] 已提交解析任务: {doc_id}")

    deadline = time.time() + timeout_seconds
    progress_log: List[Dict[str, Any]] = []
    final_status = "unknown"
    final_progress = 0.0
    final_message = ""
    while time.time() < deadline:
        status, progress, message, raw = get_progress(base_url, doc_id)
        final_status = status
        final_progress = progress
        final_message = message
        progress_log.append(
            {
                "time": now_str(),
                "status": status,
                "progress": round(progress, 4),
                "message": message,
                "raw": raw,
            }
        )
        print(f"[{now_str()}] 进度 {doc_id}: status={status}, progress={progress:.2%}, msg={message}")
        if status in {"completed", "failed"}:
            break
        time.sleep(poll_seconds)

    result["progress_log"] = progress_log
    result["final_status"] = final_status
    result["final_progress"] = final_progress
    result["final_message"] = final_message

    detail_ret = get_file_detail(base_url, doc_id)
    result["file_detail_response"] = detail_ret
    detail_data = (detail_ret.get("data", {}) or {}).get("data", {})
    result["chunk_size_db"] = detail_data.get("chunk_size", 0) if isinstance(detail_data, dict) else 0
    result["is_chunked_db"] = detail_data.get("is_chunked", False) if isinstance(detail_data, dict) else False

    chunks = load_local_chunks(project_root, doc_id)
    result["chunk_size_file"] = len(chunks)
    result["chunk_preview"] = preview_chunks(chunks, limit=5)
    result["ok"] = final_status == "completed" and len(chunks) > 0
    result["ended_at"] = now_str()

    out_path = out_dir / f"{doc_id}.result.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[{now_str()}] 测试结果已写入: {out_path}")
    return result


def find_test_files(test_data_dir: Path) -> List[Path]:
    files: List[Path] = []
    for p in sorted(test_data_dir.iterdir()):
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
            files.append(p)
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description="知识库上传+解析接口联调测试脚本")
    parser.add_argument("--base-url", default="http://127.0.0.1:5000", help="后端服务地址")
    parser.add_argument("--poll-seconds", type=int, default=2, help="进度轮询间隔秒数")
    parser.add_argument("--timeout-seconds", type=int, default=300, help="单文件超时时间")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parents[2]
    test_data_dir = script_dir / "test_data"
    out_dir = script_dir / "results"
    test_data_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = find_test_files(test_data_dir)
    if not files:
        print(f"[{now_str()}] test_data 目录没有可测试文件: {test_data_dir}")
        print("支持扩展名: .pdf .doc .docx .txt .md")
        return

    print(f"[{now_str()}] 测试开始，文件数量: {len(files)}，base_url={args.base_url}")
    all_results: List[Dict[str, Any]] = []
    for file_path in files:
        one = run_one_file(
            base_url=args.base_url,
            project_root=project_root,
            file_path=file_path,
            out_dir=out_dir,
            poll_seconds=max(1, args.poll_seconds),
            timeout_seconds=max(30, args.timeout_seconds),
        )
        all_results.append(one)

    summary = {
        "generated_at": now_str(),
        "base_url": args.base_url,
        "total": len(all_results),
        "success": sum(1 for x in all_results if x.get("ok")),
        "failed": sum(1 for x in all_results if not x.get("ok")),
        "results": all_results,
    }
    summary_path = out_dir / f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[{now_str()}] 测试完成，汇总文件: {summary_path}")


if __name__ == "__main__":
    main()
