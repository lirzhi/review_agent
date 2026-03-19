import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional


class CTDSectionService:
    """Chemical drug pharmacy CTD/eCTD Module 3 section catalog."""

    SECTION_CODE_RE = re.compile(r"3\.2\.[SP](?:\.\d+){1,2}", re.IGNORECASE)

    def __init__(self, raw_data_dir: str):
        self.raw_data_dir = Path(raw_data_dir)
        self._catalog_cache: Optional[Dict[str, Any]] = None

    def _load_json(self, filename: str) -> List[Dict[str, Any]]:
        path = self.raw_data_dir / filename
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []

    def _normalize_nodes(
        self,
        nodes: List[Dict[str, Any]],
        parent_path: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        parent_path = parent_path or []
        out: List[Dict[str, Any]] = []
        for node in nodes or []:
            if not isinstance(node, dict):
                continue
            section_id = str(node.get("section_id", "")).strip()
            if not section_id:
                continue
            section_name = str(node.get("section_name", "")).strip() or section_id
            points = [str(x).strip() for x in (node.get("points") or []) if str(x).strip()]
            title_path = parent_path + [section_name]
            children = self._normalize_nodes(node.get("children_sections") or [], title_path)
            out.append(
                {
                    "section_id": section_id,
                    "section_code": section_id,
                    "section_name": section_name,
                    "title_path": title_path,
                    "concern_points": points,
                    "children_sections": children,
                }
            )
        return out

    def _flatten_nodes(
        self,
        nodes: List[Dict[str, Any]],
        parent_section_id: str = "",
    ) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for node in nodes or []:
            current = {
                "section_id": node["section_id"],
                "section_code": node["section_code"],
                "section_name": node["section_name"],
                "title_path": list(node.get("title_path") or []),
                "concern_points": list(node.get("concern_points") or []),
                "parent_section_id": parent_section_id or "",
                "children_sections": [],
            }
            out.append(current)
            out.extend(self._flatten_nodes(node.get("children_sections") or [], node["section_id"]))
        return out

    def _build_catalog(self) -> Dict[str, Any]:
        api_nodes = self._normalize_nodes(self._load_json("原料药关注点.json"))
        fpp_nodes = self._normalize_nodes(self._load_json("制剂关注点.json"))
        roots = [
            {
                "section_id": "3.2.S",
                "section_code": "3.2.S",
                "section_name": "原料药",
                "title_path": ["原料药"],
                "concern_points": [],
                "children_sections": api_nodes,
            },
            {
                "section_id": "3.2.P",
                "section_code": "3.2.P",
                "section_name": "制剂",
                "title_path": ["制剂"],
                "concern_points": [],
                "children_sections": fpp_nodes,
            },
        ]
        flat = self._flatten_nodes(roots)
        return {
            "chapter_structure": roots,
            "flat_sections": flat,
            "section_map": {item["section_id"]: item for item in flat},
        }

    def get_catalog(self) -> Dict[str, Any]:
        if self._catalog_cache is None:
            self._catalog_cache = self._build_catalog()
        return {
            "chapter_structure": deepcopy(self._catalog_cache["chapter_structure"]),
            "flat_sections": deepcopy(self._catalog_cache["flat_sections"]),
            "section_map": deepcopy(self._catalog_cache["section_map"]),
        }

    def get_section(self, section_id: str) -> Optional[Dict[str, Any]]:
        section_key = str(section_id or "").strip()
        if not section_key:
            return None
        return self.get_catalog()["section_map"].get(section_key)

    def list_section_ids(self) -> List[str]:
        items = self.get_catalog()["flat_sections"]
        return [str(item.get("section_id", "")).strip() for item in items if str(item.get("section_id", "")).strip()]

    def infer_section_id_from_path(self, raw_path: str) -> str:
        path = str(raw_path or "").replace("\\", "/").strip()
        if not path:
            return ""
        matches = self.SECTION_CODE_RE.findall(path)
        if matches:
            matches = sorted(set(matches), key=len, reverse=True)
            for item in matches:
                if self.get_section(item):
                    return item
        normalized = path.lower()
        candidates = sorted(self.list_section_ids(), key=len, reverse=True)
        for code in candidates:
            if code.lower() in normalized:
                return code
        return ""
