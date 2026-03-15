import os
from typing import Any, Callable, Dict, List, Optional


class ParserManager:
    _registry: Dict[str, Callable[[str], Any]] = {}

    @classmethod
    def register_parser(cls, ext: str, parser_callable: Callable[[str], Any]) -> None:
        print("[DEBUG] enter ParserManager.register_parser | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        normalized_ext = ext.lower().lstrip(".")
        cls._registry[normalized_ext] = parser_callable
        print(
            f"[ParserDebug] register_parser called: ext={normalized_ext}, "
            f"parser={getattr(parser_callable, '__name__', str(parser_callable))}"
        )

    @classmethod
    def list_supported_extensions(cls) -> List[str]:
        print("[DEBUG] enter ParserManager.list_supported_extensions | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        exts = sorted(cls._registry.keys())
        print(f"[ParserDebug] list_supported_extensions called: count={len(exts)}, exts={exts}")
        return exts

    @classmethod
    def is_supported(cls, ext: str) -> bool:
        print("[DEBUG] enter ParserManager.is_supported | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        normalized = ext.lower().lstrip(".")
        ok = normalized in cls._registry
        print(f"[ParserDebug] is_supported called: ext={ext}, normalized={normalized}, supported={ok}")
        return ok

    @classmethod
    def get_parser(cls, ext: str) -> Callable[[str], Any]:
        print("[DEBUG] enter ParserManager.get_parser | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        ext = ext.lower().lstrip(".")
        print(f"[ParserDebug] get_parser called: ext={ext}")
        if ext not in cls._registry:
            supported = ", ".join(cls.list_supported_extensions())
            print(f"[ParserDebug] get_parser failed: ext={ext}, supported={supported}")
            raise ValueError(f"No parser registered for extension: {ext} (supported: {supported})")
        print(f"[ParserDebug] get_parser success: ext={ext}")
        return cls._registry[ext]

    @classmethod
    def parse(cls, file_path: str, ext_hint: Optional[str] = None) -> List[dict]:
        print("[DEBUG] enter ParserManager.parse | core:", {k: ((v[:100] + "...") if isinstance(v, str) and len(v) > 100 else v) for k, v in locals().items() if k in ("project_id", "doc_id", "file_path", "file_name", "file_type", "classification", "section_id", "run_id", "query", "page", "page_size", "status", "chunk_id")})
        print(f"[ParserDebug] parse called: file_path={file_path}, ext_hint={ext_hint}")
        if not os.path.exists(file_path):
            print(f"[ParserDebug] parse failed: file not found -> {file_path}")
            raise FileNotFoundError(f"file not found: {file_path}")
        ext = os.path.splitext(file_path)[1].lstrip(".").lower()
        if not ext and ext_hint:
            ext = str(ext_hint).lstrip(".").lower()
        print(f"[ParserDebug] parse resolved extension: ext={ext}")
        parser = cls.get_parser(ext)
        result = parser(file_path)
        if not isinstance(result, list):
            print(f"[ParserDebug] parse failed: parser return type={type(result)}")
            raise TypeError("Parser must return list[dict]")
        print(f"[ParserDebug] parse success: chunk_count={len(result)}")
        return result
