import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps
from typing import Any, Callable


class ResponseMessage:
    def __init__(self, code: int, message: str, data: Any = None):
        print("[DEBUG] enter ResponseMessage.__init__ | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        self.code = code
        self.message = message
        self.data = data

    def to_dict(self) -> dict:
        print("[DEBUG] enter ResponseMessage.to_dict | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        return {"code": self.code, "message": self.message, "data": self.data}

    def to_json(self) -> str:
        print("[DEBUG] enter ResponseMessage.to_json | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        return json.dumps(self.to_dict(), ensure_ascii=False)


def parallelize_processing(field_to_iterate: str, result_field: str, max_workers: int = 8):
    """
    Generic parallel helper for list fields in a state dict.
    """
    print("[DEBUG] enter parallelize_processing | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})

    def decorator(func: Callable):
        print("[DEBUG] enter parallelize_processing.decorator | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        @wraps(func)
        def wrapper(self, data_state):
            print("[DEBUG] enter parallelize_processing.decorator.wrapper | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
            items = data_state.get(field_to_iterate, [])
            if not isinstance(items, list):
                raise ValueError(f"{field_to_iterate} must be a list")

            result_list = [None] * len(items)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(func, self, data_state, item, idx): idx for idx, item in enumerate(items)}
                for future in as_completed(futures):
                    idx = futures[future]
                    result_list[idx] = future.result()
            data_state[result_field] = result_list
            return data_state

        return wrapper

    return decorator

