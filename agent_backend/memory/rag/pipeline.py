import re
import json
from typing import Any, Dict, List, Optional, Callable

from agent.agent_backend.agents.knowledge_index_agent import KnowledgeIndexAgent
from agent.agent_backend.context.builder import ContextBuilder
from agent.agent_backend.llm.client import LLMClient
from agent.agent_backend.memory.embedding import EmbeddingService
from agent.agent_backend.memory.rag.document import DocumentProcessor
from agent.agent_backend.memory.storage.vector_store import VectorStore


class RAGPipeline:
    """
    Hybrid RAG pipeline:
    1) parse and index chunks
    2) vector retrieve
    3) lexical rerank
    4) build compact context (GSSC)
    """

    def __init__(self):
        self.processor = DocumentProcessor()
        self.index_agent = KnowledgeIndexAgent()
        self.llm = LLMClient()
        self.embedding = EmbeddingService()
        self.store = VectorStore()
        self.ctx_builder = ContextBuilder()
        self._indexed_docs: set[str] = set()

    @staticmethod
    def _query_terms(query: str) -> list[str]:
        query = (query or "").lower()
        terms = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]", query)
        return [t for t in terms if t]

    @staticmethod
    def _lexical_score(query_terms: list[str], text: str) -> float:
        if not query_terms:
            return 0.0
        low = (text or "").lower()
        hit = sum(1 for t in query_terms if t in low)
        return hit / len(query_terms)

    @staticmethod
    def _parse_chunk_order(chunk_id: str) -> int:
        m = re.search(r"(\d+)$", str(chunk_id or ""))
        return int(m.group(1)) if m else 10**9

    def _doc_related_chunks(self, doc_id: str, anchor_chunk_id: str = "", window: int = 2, limit: int = 6) -> List[Dict[str, Any]]:
        rows = self.store.list_by_doc(doc_id)
        chunks = [r for r in rows if (r.get("metadata") or {}).get("item_type") == "chunk"]
        if not chunks:
            return []
        anchor_order = self._parse_chunk_order(anchor_chunk_id) if anchor_chunk_id else None
        selected = chunks
        if anchor_order is not None and anchor_order < 10**9:
            selected = [
                r
                for r in chunks
                if abs(int((r.get("metadata") or {}).get("chunk_order", 10**9)) - anchor_order) <= window
            ] or chunks
        selected = selected[:limit]
        out = []
        for r in selected:
            md = r.get("metadata") or {}
            out.append(
                {
                    "chunk_id": md.get("chunk_id"),
                    "chunk_order": md.get("chunk_order"),
                    "page": md.get("page"),
                    "summary": md.get("summary", ""),
                    "text": str(r.get("text", ""))[:500],
                }
            )
        return out

    def _doc_summary_meta(self, doc_id: str) -> Dict[str, Any]:
        rows = self.store.list_by_doc(doc_id)
        for r in rows:
            md = r.get("metadata") or {}
            if md.get("item_type") == "doc_summary":
                return {
                    "summary": md.get("summary", ""),
                    "keywords": md.get("keywords", []),
                    "text": r.get("text", ""),
                }
        return {"summary": "", "keywords": [], "text": ""}

    def index_file(
        self,
        file_path: str,
        doc_id: str,
        classification: str = "",
        force: bool = False,
        file_type: str = "",
        parsed_output_path: str = "",
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> int:
        if (doc_id in self._indexed_docs) and not force:
            return 0
        if force:
            self.store.delete_by_doc(doc_id)
        if progress_callback:
            progress_callback(0.05, "开始读取并分块")

        chunks = self.processor.process(file_path, file_type=file_type)
        if progress_callback:
            progress_callback(0.2, f"分块完成，共 {len(chunks)} 块")
        parsed_rows: list[dict] = []
        chunk_enrich_rows: list[dict] = []
        total = max(1, len(chunks))
        for idx, c in enumerate(chunks, start=1):
            text = c["text"]
            enrich = self.index_agent.analyze_chunk(text)
            summary = str(enrich.get("summary", "")).strip()
            keywords = enrich.get("keywords", [])
            if not isinstance(keywords, list):
                keywords = []
            keyword_text = " ".join([str(x).strip() for x in keywords if str(x).strip()])
            vec = self.embedding.embed(text)
            chunk_key = f"{doc_id}:{c['chunk_id']}"
            metadata = {
                "doc_id": doc_id,
                "chunk_id": c["chunk_id"],
                "item_type": "chunk",
                "chunk_order": self._parse_chunk_order(c["chunk_id"]),
                "page": c.get("page"),
                "page_start": c.get("page_start"),
                "page_end": c.get("page_end"),
                "section_id": c.get("section_id"),
                "section_code": c.get("section_code"),
                "section_name": c.get("section_name"),
                "unit_type": c.get("unit_type"),
                "char_count": c.get("char_count", len(text)),
                "source_chunk_ids": c.get("source_chunk_ids", []),
                "classification": classification,
                "summary": summary,
                "keywords": keywords,
                "keyword_text": keyword_text,
            }
            self.store.add(chunk_key, vec, text, metadata=metadata)
            chunk_enrich_rows.append(
                {
                    "chunk_id": c.get("chunk_id"),
                    "summary": summary,
                    "keywords": keywords,
                    "text": text[:400],
                }
            )
            parsed_rows.append(
                {
                    "chunk_id": c.get("chunk_id"),
                    "page": c.get("page"),
                    "page_start": c.get("page_start"),
                    "page_end": c.get("page_end"),
                    "section_id": c.get("section_id"),
                    "section_code": c.get("section_code"),
                    "section_name": c.get("section_name"),
                    "unit_type": c.get("unit_type"),
                    "char_count": c.get("char_count", len(text)),
                    "source_chunk_ids": c.get("source_chunk_ids", []),
                    "classification": classification,
                    "summary": summary,
                    "keywords": keywords,
                    "text": text,
                }
            )
            if progress_callback:
                progress_callback(0.2 + (0.7 * idx / total), f"已处理分块 {idx}/{total}")

        if progress_callback:
            progress_callback(0.92, "生成整文摘要")
        doc_enrich = self.index_agent.analyze_document(
            title=str(doc_id),
            chunks=chunk_enrich_rows,
        )
        doc_summary_text = str(doc_enrich.get("summary", "")).strip()
        doc_keywords = doc_enrich.get("keywords", [])
        if not isinstance(doc_keywords, list):
            doc_keywords = []
        if doc_summary_text:
            doc_vec = self.embedding.embed(doc_summary_text)
            self.store.add(
                f"{doc_id}:__doc_summary__",
                doc_vec,
                doc_summary_text,
                metadata={
                    "doc_id": doc_id,
                    "chunk_id": "__doc_summary__",
                    "item_type": "doc_summary",
                    "chunk_order": 0,
                    "classification": classification,
                    "summary": doc_summary_text,
                    "keywords": doc_keywords,
                    "keyword_text": " ".join([str(x).strip() for x in doc_keywords if str(x).strip()]),
                },
            )
        parsed_rows.insert(
            0,
            {
                "chunk_id": "__doc_summary__",
                "item_type": "doc_summary",
                "summary": doc_summary_text,
                "keywords": doc_keywords,
                "text": doc_summary_text,
            },
        )

        if parsed_output_path:
            if progress_callback:
                progress_callback(0.97, "写入解析结果")
            with open(parsed_output_path, "w", encoding="utf-8") as f:
                json.dump(parsed_rows, f, ensure_ascii=False, indent=2)
        self._indexed_docs.add(doc_id)
        if progress_callback:
            progress_callback(1.0, "解析完成")
        return len(chunks)

    def index_preparsed(
        self,
        doc_id: str,
        parsed_rows: List[Dict[str, Any]],
        classification: str = "",
        force: bool = False,
    ) -> int:
        """
        Rebuild vector index from saved parsed JSON rows without re-parsing source file.
        """
        if (doc_id in self._indexed_docs) and not force:
            return 0
        if force:
            self.store.delete_by_doc(doc_id)

        count = 0
        for row in parsed_rows or []:
            if not isinstance(row, dict):
                continue
            chunk_id = str(row.get("chunk_id", "")).strip()
            if not chunk_id:
                continue

            item_type = str(row.get("item_type", "chunk") or "chunk")
            text = str(row.get("text", "")).strip()
            if not text:
                continue

            if item_type == "doc_summary":
                summary = str(row.get("summary", "") or text).strip()
                keywords = row.get("keywords", [])
                if not isinstance(keywords, list):
                    keywords = []
                vec = self.embedding.embed(summary)
                self.store.add(
                    f"{doc_id}:__doc_summary__",
                    vec,
                    summary,
                    metadata={
                        "doc_id": doc_id,
                        "chunk_id": "__doc_summary__",
                        "item_type": "doc_summary",
                        "chunk_order": 0,
                        "classification": classification,
                        "summary": summary,
                        "keywords": keywords,
                        "keyword_text": " ".join([str(x).strip() for x in keywords if str(x).strip()]),
                    },
                )
                count += 1
                continue

            summary = str(row.get("summary", "")).strip()
            keywords = row.get("keywords", [])
            if not isinstance(keywords, list):
                keywords = []
            vec = self.embedding.embed(text)
            self.store.add(
                f"{doc_id}:{chunk_id}",
                vec,
                text,
                metadata={
                    "doc_id": doc_id,
                    "chunk_id": chunk_id,
                    "item_type": "chunk",
                    "chunk_order": self._parse_chunk_order(chunk_id),
                    "page": row.get("page"),
                    "page_start": row.get("page_start", row.get("page")),
                    "page_end": row.get("page_end", row.get("page")),
                    "section_id": row.get("section_id"),
                    "section_code": row.get("section_code"),
                    "section_name": row.get("section_name"),
                    "unit_type": row.get("unit_type"),
                    "char_count": row.get("char_count", len(text)),
                    "source_chunk_ids": row.get("source_chunk_ids", []),
                    "classification": classification,
                    "summary": summary,
                    "keywords": keywords,
                    "keyword_text": " ".join([str(x).strip() for x in keywords if str(x).strip()]),
                },
            )
            count += 1

        if count > 0:
            self._indexed_docs.add(doc_id)
        return count

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        alpha: float = 0.75,
        min_score: float = 0.6,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        qv = self.embedding.embed(query)
        vec_hits = self.store.search(qv, top_k=max(top_k * 4, 20), filters=filters or {})
        terms = self._query_terms(query)

        reranked = []
        texts_for_rerank = [str(h.get("text", "")) for h in vec_hits]
        rerank_scores = self.llm.rerank(query=query, documents=texts_for_rerank) if vec_hits else []
        for h in vec_hits:
            metadata = (h.get("metadata") or {})
            text_lex = self._lexical_score(terms, h.get("text", ""))
            summary_lex = self._lexical_score(terms, str(metadata.get("summary", "")))
            keyword_lex = self._lexical_score(terms, str(metadata.get("keyword_text", "")))
            lexical = min(1.0, 0.55 * text_lex + 0.20 * summary_lex + 0.25 * keyword_lex)
            vec_score = float(h.get("score", 0.0))
            idx = len(reranked)
            model_rerank = float(rerank_scores[idx]) if idx < len(rerank_scores) else lexical
            final_score = alpha * vec_score + (1 - alpha) * model_rerank
            reranked.append(
                {
                    "id": h["id"],
                    "doc_id": metadata.get("doc_id"),
                    "chunk_id": metadata.get("chunk_id"),
                    "item_type": metadata.get("item_type", "chunk"),
                    "chunk_order": metadata.get("chunk_order"),
                    "page": metadata.get("page"),
                    "page_start": metadata.get("page_start"),
                    "page_end": metadata.get("page_end"),
                    "section_id": metadata.get("section_id"),
                    "section_code": metadata.get("section_code"),
                    "section_name": metadata.get("section_name"),
                    "unit_type": metadata.get("unit_type"),
                    "char_count": metadata.get("char_count"),
                    "classification": metadata.get("classification"),
                    "summary": metadata.get("summary"),
                    "keywords": metadata.get("keywords") or [],
                    "vector_score": vec_score,
                    "lexical_score": lexical,
                    "rerank_score": model_rerank,
                    "score": final_score,
                    "text": h.get("text", ""),
                }
            )
        reranked.sort(key=lambda x: x["score"], reverse=True)
        filtered = [x for x in reranked if float(x.get("score", 0.0)) >= float(min_score)]
        top_hits = filtered[:top_k]
        for h in top_hits:
            doc_id = str(h.get("doc_id", "") or "")
            if not doc_id:
                h["related_chunks"] = []
                h["doc_summary"] = ""
                h["doc_keywords"] = []
                continue
            doc_meta = self._doc_summary_meta(doc_id)
            h["doc_summary"] = doc_meta.get("summary", "")
            h["doc_keywords"] = doc_meta.get("keywords", [])
            anchor = "" if h.get("item_type") == "doc_summary" else str(h.get("chunk_id", "") or "")
            h["related_chunks"] = self._doc_related_chunks(doc_id=doc_id, anchor_chunk_id=anchor)
        return top_hits

    def build_context(
        self,
        query: str,
        top_k: int = 6,
        alpha: float = 0.75,
        min_score: float = 0.6,
        max_chars: int = 1600,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        hits = self.retrieve(
            query=query,
            top_k=top_k,
            alpha=alpha,
            min_score=min_score,
            filters=filters,
        )
        sources = [
            {
                "text": h["text"],
                "score": h["score"],
                "source": f"{h.get('doc_id')}/{h.get('chunk_id')}",
                "metadata": {
                    "doc_id": h.get("doc_id"),
                    "chunk_id": h.get("chunk_id"),
                    "page_start": h.get("page_start"),
                    "page_end": h.get("page_end"),
                },
            }
            for h in hits
        ]
        gssc = self.ctx_builder.build(sources=sources, max_items=top_k)
        compressed = gssc.compressed[:max_chars]
        return {
            "query": query,
            "hits": hits,
            "context": compressed,
            "references": [
                {
                    "doc_id": h["doc_id"],
                    "chunk_id": h["chunk_id"],
                    "page": h["page"],
                    "score": h["score"],
                }
                for h in hits
            ],
        }
