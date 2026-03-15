import json
import os
import time
from datetime import datetime
from pathlib import Path

import requests


# ===== 手动在这里改参数 =====
PDF_PATH = r"高变异药物生物等效性研究技术指导原则.pdf"
TOOL_TYPE = "lite"
FILE_TYPE = "PDF"
MAX_POLLS = 60
POLL_SECONDS = 2
# ==========================

CREATE_URL = "https://open.bigmodel.cn/api/paas/v4/files/parser/create"
RESULT_URL = "https://open.bigmodel.cn/api/paas/v4/files/parser/result/{task_id}/text"


def get_api_key(project_root: Path) -> str:
    key = os.getenv("ZHIPU_API_KEY", "").strip()
    if key:
        return key
    key_file = project_root / "agent" / "agent_backend" / "llm" / "temp" / "key" / "glm_key"
    if key_file.exists():
        key = key_file.read_text(encoding="utf-8").strip()
        if key:
            return key
    raise RuntimeError("未找到 API Key，请设置 ZHIPU_API_KEY 或填写 glm_key 文件")


def main() -> None:
    pdf_path = Path(PDF_PATH).expanduser().resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF 不存在: {pdf_path}")

    test_dir = Path(__file__).resolve().parent
    project_root = test_dir.parents[2]
    out_dir = test_dir / "results"
    out_dir.mkdir(parents=True, exist_ok=True)

    api_key = get_api_key(project_root)
    headers = {"Authorization": f"Bearer {api_key}"}

    with pdf_path.open("rb") as f:
        files = {"file": (pdf_path.name, f, "application/pdf")}
        data = {"tool_type": TOOL_TYPE, "file_type": FILE_TYPE}
        create_resp = requests.post(CREATE_URL, headers=headers, data=data, files=files, timeout=180)

    try:
        create_json = create_resp.json()
    except Exception:
        raise RuntimeError(f"创建任务失败: {create_resp.text}")

    task_id = (
        create_json.get("task_id")
        or create_json.get("taskId")
        or create_json.get("id")
        or (create_json.get("data") or {}).get("task_id")
    )
    if not task_id:
        raise RuntimeError(f"创建任务后未返回 task_id: {create_json}")

    result_resp = None
    for _ in range(MAX_POLLS):
        result_resp = requests.get(RESULT_URL.format(task_id=task_id), headers=headers, timeout=60)
        if result_resp.status_code == 200:
            break
        time.sleep(POLL_SECONDS)

    try:
        result_body = result_resp.json() if result_resp is not None else {}
        print("识别结果：", result_resp.status_code if result_resp else "No response", result_body)
    except Exception:
        result_body = {"raw_text": result_resp.text if result_resp else ""}

    output = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "file": str(pdf_path),
        "task_id": task_id,
        "create": create_json,
        "result": result_body,
    }
    out_path = out_dir / f"{pdf_path.stem}.glm_ocr_simple.json"
    pretty_json = json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    out_path.write_text(pretty_json, encoding="utf-8")

    print(f"文件: {pdf_path.name}")
    print(f"任务ID: {task_id}")
    print(f"结果已写入: {out_path}")


if __name__ == "__main__":
    main()
