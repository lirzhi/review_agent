import json
import math
import re
from typing import Dict, List, Optional, Tuple

from agent.agent_backend.llm.client import LLMClient
from agent.agent_backend.prompts.template_manager import PromptTemplateManager
from agent.agent_backend.utils.parser import ParserManager


class DocumentProcessor:
    """
    RAG preprocessing strategy:
    1) parser extracts raw document units
    2) merge raw units into full document text
    3) LLM performs semantic segmentation on full text
    4) fallback to deterministic segmentation when needed
    5) map each segment back to page/source metadata
    """

    def __init__(
        self,
        target_chunk_chars: int = 700,
        max_chunk_chars: int = 900,
        min_chunk_chars: int = 120,
    ):
        self.target_chunk_chars = target_chunk_chars
        self.max_chunk_chars = max_chunk_chars
        self.min_chunk_chars = min_chunk_chars
        self.llm = LLMClient()
        self.prompts = PromptTemplateManager("knowledge_parse_agent_prompt")

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = (text or "").replace("\u3000", " ")
        text = re.sub(r"\r\n?", "\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def _sentence_split(text: str) -> List[str]:
        if not text:
            return []
        parts = re.split(r"(?<=[。！？；.!?;])\s+|\n{2,}", text)
        out = [p.strip() for p in parts if p and p.strip()]
        return out if out else [text]

    def _split_long_text(self, text: str, limit: Optional[int] = None) -> List[str]:
        max_len = int(limit or self.max_chunk_chars)
        text = self._normalize_text(text)
        if not text:
            return []
        if len(text) <= max_len:
            return [text]

        segments: List[str] = []
        cur = ""
        for sent in self._sentence_split(text):
            if len(sent) > max_len:
                if cur:
                    segments.append(cur)
                    cur = ""
                for i in range(0, len(sent), max_len):
                    piece = sent[i : i + max_len].strip()
                    if piece:
                        segments.append(piece)
                continue
            if len(cur) + len(sent) + 1 <= max_len:
                cur = f"{cur} {sent}".strip()
            else:
                if cur:
                    segments.append(cur)
                cur = sent
        if cur:
            segments.append(cur)
        return segments

    def _normalize_raw_units(self, raw_chunks: List[Dict]) -> List[Dict]:
        units: List[Dict] = []
        for idx, item in enumerate(raw_chunks or [], start=1):
            if not isinstance(item, dict):
                continue
            text = self._normalize_text(str(item.get("text", "")))
            if not text:
                continue
            page = item.get("page")
            units.append(
                {
                    "text": text,
                    "page": page if isinstance(page, int) else None,
                    "source_chunk_id": str(item.get("chunk_id", idx)),
                }
            )
        return units

    def _compose_full_text(self, units: List[Dict]) -> Tuple[str, List[Dict]]:
        """
        Return:
        - full_text
        - spans: [{start, end, page, source_chunk_id, text}]
        """
        full_parts: List[str] = []
        spans: List[Dict] = []
        cursor = 0
        for i, u in enumerate(units):
            text = u["text"]
            if i > 0:
                sep = "\n\n"
                full_parts.append(sep)
                cursor += len(sep)
            start = cursor
            full_parts.append(text)
            cursor += len(text)
            end = cursor
            spans.append(
                {
                    "start": start,
                    "end": end,
                    "page": u.get("page"),
                    "source_chunk_id": u.get("source_chunk_id"),
                    "text": text,
                }
            )
        return "".join(full_parts), spans

    def _llm_chunk_once(self, text: str) -> List[str]:
        text = self._normalize_text(text)
        if not text:
            return []

        fallback = self._split_long_text(text, limit=self.max_chunk_chars)
        prompt = self.prompts.render(
            "semantic_chunk.j2",
            {
                "min_chars": max(self.min_chunk_chars, self.target_chunk_chars - 120),
                "max_chars": self.max_chunk_chars,
                "text": text,
            },
        )
        raw = self.llm.chat(
            messages=[
                {"role": "system", "content": self.prompts.render("system_json_only.j2", {})},
                {"role": "user", "content": prompt},
            ],
            default=json.dumps(fallback, ensure_ascii=False),
        )
        data = self.llm.extract_json(raw)
        if not isinstance(data, list):
            return fallback
        out: List[str] = []
        for x in data:
            seg = self._normalize_text(str(x))
            if not seg:
                continue
            if len(seg) > self.max_chunk_chars:
                out.extend(self._split_long_text(seg, limit=self.max_chunk_chars))
            else:
                out.append(seg)
        return out if out else fallback

    def _semantic_chunk_full_text(self, full_text: str) -> List[str]:
        """
        Prefer one-shot full-text segmentation.
        If the text exceeds model context budget, split into windows and merge.
        """
        full_text = self._normalize_text(full_text)
        if not full_text:
            return []

        budget = max(4000, int(self.llm.chat_context_max_chars * 0.9))
        if len(full_text) <= budget:
            segs = self._llm_chunk_once(full_text)
            if self._is_valid_segments(segs, full_text):
                return self._merge_small_segments(segs)
            return self._merge_small_segments(self._split_long_text(full_text, limit=self.max_chunk_chars))

        window_size = max(5000, budget)
        merged: List[str] = []
        for i in range(0, len(full_text), window_size):
            piece = full_text[i : i + window_size]
            piece_segs = self._llm_chunk_once(piece)
            if not self._is_valid_segments(piece_segs, piece):
                piece_segs = self._split_long_text(piece, limit=self.max_chunk_chars)
            merged.extend(piece_segs)
        return self._merge_small_segments(merged)

    def _is_valid_segments(self, segments: List[str], full_text: str) -> bool:
        if not segments:
            return False
        cleaned = [self._normalize_text(x) for x in segments if self._normalize_text(x)]
        if not cleaned:
            return False
        total = sum(len(x) for x in cleaned)
        full_len = max(1, len(full_text))
        ratio = total / full_len
        if ratio < 0.45 or ratio > 1.8:
            return False
        return True

    def _merge_small_segments(self, segments: List[str]) -> List[str]:
        out: List[str] = []
        cur = ""
        for seg in [self._normalize_text(x) for x in segments if self._normalize_text(x)]:
            if not cur:
                cur = seg
                continue
            if len(cur) < self.min_chunk_chars:
                cur = f"{cur} {seg}".strip()
                if len(cur) > self.max_chunk_chars:
                    out.extend(self._split_long_text(cur, limit=self.max_chunk_chars))
                    cur = ""
                continue
            out.append(cur)
            cur = seg
        if cur:
            if out and len(cur) < self.min_chunk_chars:
                out[-1] = f"{out[-1]} {cur}".strip()
            else:
                out.append(cur)
        final: List[str] = []
        for x in out:
            if len(x) > self.max_chunk_chars:
                final.extend(self._split_long_text(x, limit=self.max_chunk_chars))
            else:
                final.append(x)
        return final

    @staticmethod
    def _overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
        return max(0, min(a_end, b_end) - max(a_start, b_start))

    def _segment_meta_by_ratio(self, segments: List[str], spans: List[Dict], full_text_len: int) -> List[Dict]:
        """
        Map segment metadata by proportional position in full text.
        This is robust when LLM keeps order but slightly rewrites punctuation.
        """
        if not segments:
            return []
        total_seg_len = max(1, sum(len(s) for s in segments))
        consumed = 0
        mapped: List[Dict] = []

        for seg in segments:
            seg_len = max(1, len(seg))
            start = int(math.floor(full_text_len * consumed / total_seg_len))
            consumed += seg_len
            end = int(math.floor(full_text_len * consumed / total_seg_len))
            if end <= start:
                end = min(full_text_len, start + seg_len)

            touched = []
            for sp in spans:
                ov = self._overlap(start, end, int(sp["start"]), int(sp["end"]))
                if ov > 0:
                    touched.append((ov, sp))
            touched.sort(key=lambda x: (-x[0], int(x[1]["start"])))
            span_only = [x[1] for x in touched]

            pages = [s.get("page") for s in span_only if isinstance(s.get("page"), int)]
            source_ids = [str(s.get("source_chunk_id")) for s in span_only if s.get("source_chunk_id")]

            mapped.append(
                {
                    "text": seg,
                    "page": min(pages) if pages else None,
                    "page_start": min(pages) if pages else None,
                    "page_end": max(pages) if pages else None,
                    "source_chunk_ids": sorted(set(source_ids)),
                }
            )
        return mapped

    def process(self, file_path: str, file_type: str = "") -> List[Dict]:
        raw_chunks = ParserManager.parse(file_path, ext_hint=file_type)
        units = self._normalize_raw_units(raw_chunks)
        if not units:
            return []

        full_text, spans = self._compose_full_text(units)
        if not full_text:
            return []

        llm_segments = self._semantic_chunk_full_text(full_text)
        if not llm_segments:
            llm_segments = self._split_long_text(full_text, limit=self.max_chunk_chars)
        llm_segments = self._merge_small_segments(llm_segments)
        if not llm_segments:
            return []

        chunk_meta = self._segment_meta_by_ratio(
            segments=llm_segments,
            spans=spans,
            full_text_len=len(full_text),
        )
        result: List[Dict] = []
        for idx, item in enumerate(chunk_meta, start=1):
            text = self._normalize_text(str(item.get("text", "")))
            if not text:
                continue
            result.append(
                {
                    "chunk_id": f"rag_{idx}",
                    "page": item.get("page"),
                    "page_start": item.get("page_start"),
                    "page_end": item.get("page_end"),
                    "text": text,
                    "char_count": len(text),
                    "source_chunk_ids": item.get("source_chunk_ids", []),
                }
            )
        return result
