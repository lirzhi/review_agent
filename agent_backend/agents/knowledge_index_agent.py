import re
from collections import Counter
from typing import Dict, List

from agent.agent_backend.llm.client import LLMClient
from agent.agent_backend.prompts.template_manager import PromptTemplateManager


class KnowledgeIndexAgent:
    """
    知识库解析 Agent：
    - 分块摘要提取
    - 分块关键词提取
    - 整文摘要与整文关键词提取
    """

    def __init__(self):
        self.llm = LLMClient()
        self.prompts = PromptTemplateManager("knowledge_parse_agent_prompt")

    @staticmethod
    def _fallback_keywords(text: str, top_k: int = 8) -> List[str]:
        tokens = re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,}|[\u4e00-\u9fff]{2,}", text or "")
        if not tokens:
            return []
        stop = {
            "我们",
            "你们",
            "他们",
            "以及",
            "相关",
            "进行",
            "其中",
            "包括",
            "根据",
            "这个",
            "那个",
            "可以",
        }
        terms = [t for t in tokens if t not in stop]
        freq = Counter(terms)
        return [x for x, _ in freq.most_common(top_k)]

    def analyze_chunk(self, text: str) -> Dict[str, object]:
        source = (text or "").strip()
        if not source:
            return {"summary": "", "keywords": []}

        prompt = self.prompts.render("chunk_enrich.j2", {"text": source[:3200]})
        default_summary = source[:120]
        default_keywords = self._fallback_keywords(source, top_k=8)
        raw = self.llm.chat(
            messages=[
                {"role": "system", "content": self.prompts.render("system_json_only.j2", {})},
                {"role": "user", "content": prompt},
            ],
            default=f'{{"summary":"{default_summary}","keywords":[]}}',
        )
        data = self.llm.extract_json(raw)
        if not isinstance(data, dict):
            return {"summary": default_summary, "keywords": default_keywords}

        summary = str(data.get("summary", "")).strip() or default_summary
        kws = data.get("keywords", [])
        keywords = [str(x).strip() for x in kws if str(x).strip()] if isinstance(kws, list) else []
        if not keywords:
            keywords = default_keywords

        seen = set()
        dedup: List[str] = []
        for k in keywords:
            if k in seen:
                continue
            seen.add(k)
            dedup.append(k)
        return {"summary": summary[:240], "keywords": dedup[:12]}

    def analyze_document(self, title: str, chunks: List[Dict[str, object]]) -> Dict[str, object]:
        chunk_summaries: List[str] = []
        keyword_pool: List[str] = []
        for item in chunks:
            if not isinstance(item, dict):
                continue
            s = str(item.get("summary", "")).strip()
            if s:
                chunk_summaries.append(s)
            kws = item.get("keywords", [])
            if isinstance(kws, list):
                keyword_pool.extend([str(x).strip() for x in kws if str(x).strip()])

        merged = "\n".join(chunk_summaries[:40]).strip()
        if not merged:
            merged = "\n".join([str(c.get("text", ""))[:120] for c in chunks[:20] if isinstance(c, dict)]).strip()
        if not merged:
            return {"summary": "", "keywords": []}

        prompt = self.prompts.render(
            "document_enrich.j2",
            {
                "title": title,
                "chunk_summaries": merged[:5000],
            },
        )

        fallback_keywords = self._fallback_keywords(" ".join(keyword_pool) or merged, top_k=12)
        fallback_summary = merged[:220]
        raw = self.llm.chat(
            messages=[
                {"role": "system", "content": self.prompts.render("system_json_only.j2", {})},
                {"role": "user", "content": prompt},
            ],
            default=f'{{"summary":"{fallback_summary}","keywords":[]}}',
        )
        data = self.llm.extract_json(raw)
        if not isinstance(data, dict):
            return {"summary": fallback_summary, "keywords": fallback_keywords}

        summary = str(data.get("summary", "")).strip() or fallback_summary
        kws = data.get("keywords", [])
        keywords = [str(x).strip() for x in kws if str(x).strip()] if isinstance(kws, list) else []
        if not keywords:
            keywords = fallback_keywords

        seen = set()
        dedup: List[str] = []
        for k in keywords + fallback_keywords:
            if not k or k in seen:
                continue
            seen.add(k)
            dedup.append(k)
        return {"summary": summary[:400], "keywords": dedup[:20]}
