药品审评智能系统
面向 Codex 的详细开发任务书
0. 总体要求
0.1 项目目标

基于现有 agent_backend 原型，完成以下三大能力的工程化重构：

RAG 能力增强

文件解析标准化

分块策略解耦

embedding / 检索 / 重排 / context 构建模块化

索引重建与评测脚本完善

Agent 协作增强

章节审评工作流显式化

多角色 Agent 协作

统一状态对象与输出结构

证据绑定与质控约束

反馈闭环增强

专家反馈标准化

错误归因

优化任务生成

回归案例与回放评测

0.2 开发原则

Codex 生成代码时必须遵守以下原则：

A. 先骨架，后细节

先完成：

目录结构

schema

抽象类

pipeline 骨架

方法签名

TODO 注释

复杂算法先用占位实现，保证接口稳定。

B. 所有核心模块都要有类型定义

优先使用：

dataclasses

或 pydantic（如果项目已有依赖）

不要让关键对象长期停留在裸 dict。

C. 每个方法必须有 docstring

至少说明：

作用

入参

出参

异常场景

D. 统一日志与 trace

所有 pipeline / agent / feedback 核心方法，要预留：

logger.info

logger.warning

logger.exception

trace_id / run_id / doc_id

E. 不在第一阶段引入过多新依赖

除非已有，否则先避免引入新的复杂框架。

0.3 本任务书交付范围

本任务书要求 Codex 交付：

新目录结构与基础代码骨架

所有核心 schema

RAG 骨架实现

Agent 骨架实现

Feedback 骨架实现

Application service 编排层

CLI 脚本骨架

基础单测样例

1. 阶段划分

建议按 4 个阶段实现：

阶段 1：公共基础与 schema

阶段 2：RAG 重构

阶段 3：Agent 工作流重构

阶段 4：反馈闭环与评测

每个阶段都应保证：

可单独提交

可运行最小链路

不阻塞下阶段开发

2. 阶段 1：公共基础与 Schema
任务 1.1：创建新目录骨架
目标

创建以下目录和空文件骨架。

需创建的目录
api/
api/routers/
api/schemas/

domain/
domain/entities/
domain/enums/
domain/services/

rag/
rag/parsers/
rag/chunking/
rag/indexing/
rag/retrieval/
rag/pipelines/
rag/schemas/

agents/
agents/base/
agents/roles/
agents/review/
agents/prompts/
agents/compilers/

feedback/
feedback/collection/
feedback/attribution/
feedback/optimization/
feedback/evaluation/
feedback/pipelines/

application/

infrastructure/
infrastructure/llm/
infrastructure/storage/
infrastructure/repositories/
infrastructure/logging/

scripts/
tests/
tests/rag/
tests/agents/
tests/feedback/
tests/integration/
输出要求

每个目录带 __init__.py

不删除现有旧目录

新目录与旧目录可并存

验收标准

项目可 import 新包路径

不破坏当前原型运行

任务 1.2：定义核心枚举
文件

domain/enums/doc_type_enum.py

domain/enums/review_type_enum.py

domain/enums/feedback_enum.py

domain/enums/agent_role_enum.py

要求
doc_type_enum.py

定义：

GUIDELINE

REGULATION

SUBMISSION

CASE

TEMPLATE

UNKNOWN

review_type_enum.py

定义：

PHARMACY

CLINICAL

STATISTICAL

NONCLINICAL

COMPLIANCE

GENERAL

feedback_enum.py

定义：

ACCEPTED

PARTIALLY_ACCEPTED

REJECTED

以及错误类型：

FACT_ERROR

MISSING_RISK

WRONG_REFERENCE

REASONING_ERROR

STYLE_ISSUE

COMPLIANCE_ISSUE

RETRIEVAL_MISS

CHUNKING_ISSUE

agent_role_enum.py

定义：

PLANNER

RETRIEVER

REVIEWER

REFLECTOR

SYNTHESIZER

QC

验收标准

枚举可正常 import

所有枚举值为字符串型，便于落库和序列化

任务 1.3：定义 RAG 核心 schema
文件

rag/schemas/parsed_unit.py

rag/schemas/parsed_document.py

rag/schemas/chunk_schema.py

rag/schemas/retrieval_query.py

rag/schemas/retrieval_result.py

rag/schemas/context_schema.py

parsed_unit.py

定义 ParsedUnit

字段：

unit_id: str

text: str

page_no: int | None = None

section_title: str | None = None

section_path: list[str] | None = None

unit_type: str = "text"

metadata: dict = field(default_factory=dict)

方法：

to_dict() -> dict

from_dict(data: dict) -> ParsedUnit

parsed_document.py

定义 ParsedDocument

字段：

doc_id: str

doc_type: str

title: str

version: str | None = None

source_path: str = ""

raw_units: list[ParsedUnit] = field(default_factory=list)

metadata: dict = field(default_factory=dict)

方法：

to_dict() -> dict

from_dict(data: dict) -> ParsedDocument

get_full_text() -> str

chunk_schema.py

定义 Chunk

字段：

chunk_id: str

doc_id: str

doc_type: str

text: str

chunk_type: str = "semantic"

section_id: str | None = None

section_path: list[str] | None = None

page_start: int | None = None

page_end: int | None = None

token_count: int = 0

metadata: dict = field(default_factory=dict)

方法：

to_dict() -> dict

from_dict(data: dict) -> Chunk

retrieval_query.py

定义 RetrievalQuery

字段：

query: str

task_type: str | None = None

filters: dict = field(default_factory=dict)

top_k: int = 10

max_tokens: int = 4000

metadata: dict = field(default_factory=dict)

retrieval_result.py

定义：

RetrievalHit

GroupedDocumentHit

RetrievalHit 字段：

chunk_id

doc_id

doc_title

doc_type

text

section_path

page_span

vector_score

lexical_score

rerank_score

final_score

metadata

方法：

to_dict() -> dict

context_schema.py

定义 RetrievalContext

字段：

query: str

rewritten_queries: list[str]

hits: list[RetrievalHit]

references: list[dict]

evidence_blocks: list[dict]

grouped_docs: list[dict]

used_tokens: int = 0

metadata: dict = field(default_factory=dict)

方法：

to_dict() -> dict

验收标准

所有 schema 可独立实例化

to_dict()/from_dict() 可用

单测覆盖基础序列化

任务 1.4：定义 Agent 核心 schema
文件

agents/base/agent_message.py

agents/base/agent_result.py

agents/review/review_state.py

agent_message.py

定义 AgentMessage

字段：

sender: str

receiver: str

message_type: str

content: dict | str

metadata: dict

created_at: str | None = None

方法：

to_dict() -> dict

from_dict(data: dict) -> AgentMessage

agent_result.py

定义 AgentResult

字段：

agent_name: str

success: bool

output: dict

errors: list[str]

metadata: dict

review_state.py

定义 ReviewState

字段至少包括：

run_id

project_id

submission_id

section_id

section_title

section_text

review_type

task_plan

retrieval_queries

retrieval_context

evidence_hits

draft_findings

draft_risks

draft_conclusion

reflection_notes

qc_issues

final_output

references

trace_logs

status

metadata

方法：

add_trace(step: str, payload: dict) -> None

set_plan(plan: dict) -> None

set_retrieval_result(context) -> None

set_review_output(output: dict) -> None

set_reflection_output(output: dict) -> None

set_qc_output(output: dict) -> None

finalize(output: dict) -> None

to_dict() -> dict

验收标准

ReviewState 能完整承载单章节审评状态

trace 追加正常

不依赖数据库

任务 1.5：定义 Feedback 核心 schema
文件

domain/entities/feedback_entity.py

定义对象

FeedbackRecord

RootCauseResult

FeedbackRecord

字段：

feedback_id

run_id

section_id

expert_id

decision

severity

labels

original_output

revised_output

feedback_text

diff_result

root_cause

routes

metadata

RootCauseResult

字段：

root_category

sub_category

confidence

evidence

metadata

验收标准

可表达单条反馈及归因结果

可序列化

3. 阶段 2：RAG 重构
3.1 Parser 层
任务 2.1：实现解析器抽象基类
文件

rag/parsers/base_parser.py

类

BaseParser

方法

parse(file_path: str, **kwargs) -> ParsedDocument

validate(file_path: str) -> None

normalize_metadata(raw_meta: dict) -> dict

要求

parse 作为抽象方法或显式 raise NotImplementedError

validate 检查路径、文件存在性、后缀合法性

不耦合 LLM

验收标准

可被子类继承

错误信息清晰

任务 2.2：实现 ParserRegistry
文件

rag/parsers/parser_registry.py

类

ParserRegistry

方法

register(ext: str, parser: BaseParser) -> None

get_parser(file_ext: str) -> BaseParser

list_supported_extensions() -> list[str]

is_supported(file_ext: str) -> bool

要求

ext 统一小写

未注册扩展返回明确错误

提供默认注册函数 build_default_registry()

验收标准

能注册 .pdf/.docx/.txt/.md

单测覆盖注册和查询

任务 2.3：迁移并封装 PDF 解析器
文件

rag/parsers/pdf_parser.py

类

PDFParser(BaseParser)

方法

parse(file_path: str, use_ocr: bool = False) -> ParsedDocument

_extract_pages(file_path: str) -> list[dict]

_extract_layout_units(page_obj: dict) -> list[dict]

_merge_page_units(units: list[dict]) -> list[dict]

_post_clean_units(units: list[dict]) -> list[dict]

要求

尽量复用原 utils/parser/pdf_parser.py

输出必须转成 ParsedDocument

暂不要求最优 OCR，仅保留接口

页码信息必须尽量保留

验收标准

可解析现有 PDF

返回 ParsedDocument

至少保留 page_no

任务 2.4：迁移并封装 DOCX / 文本解析器
文件

rag/parsers/docx_parser.py

rag/parsers/material_parser.py

类

DocxParser

MaterialParser

方法

DocxParser

parse(file_path: str) -> ParsedDocument

_extract_paragraph_units(file_path: str) -> list[dict]

_detect_heading_levels(units: list[dict]) -> list[dict]

MaterialParser

parse(file_path: str) -> ParsedDocument

验收标准

.docx/.txt/.md 可转为 ParsedDocument

任务 2.5：实现申报资料专用解析器
文件

rag/parsers/submission_parser.py

类

SubmissionParser(BaseParser)

方法

parse(file_path: str) -> ParsedDocument

_extract_toc(parsed_pages: list[dict]) -> list[dict]

_detect_section_boundaries(parsed_pages: list[dict]) -> list[dict]

_build_section_tree(section_hits: list[dict]) -> list[dict]

_build_review_units(section_tree: list[dict]) -> list[dict]

_attach_section_metadata(review_units: list[dict]) -> list[dict]

要求

尽量吸收原 submission_material_parser.py 的逻辑

section_path 必须作为重点字段保留下来

review unit 适配章节审评

验收标准

能输出章节化的 ParsedDocument

每个 unit 能尽量附带章节路径

3.2 Chunking 层
任务 2.6：实现 BaseChunker
文件

rag/chunking/base_chunker.py

类

BaseChunker

方法

chunk(parsed_doc: ParsedDocument) -> list[Chunk]

validate_chunks(chunks: list[Chunk]) -> list[Chunk]

merge_small_chunks(chunks: list[Chunk]) -> list[Chunk]

_estimate_tokens(text: str) -> int

要求

提供通用 chunk 校验逻辑

merge_small_chunks 先做简单合并策略即可

验收标准

子类可直接复用公共逻辑

任务 2.7：实现 RuleChunker
文件

rag/chunking/rule_chunker.py

类

RuleChunker(BaseChunker)

方法

chunk(parsed_doc: ParsedDocument) -> list[Chunk]

_split_by_heading(units: list[dict]) -> list[Chunk]

_split_by_length(text: str, max_tokens: int) -> list[str]

_attach_neighbor_info(chunks: list[Chunk]) -> list[Chunk]

适用

法规

指导原则

模板

验收标准

能按标题/长度生成 chunk

chunk 带 section_path

任务 2.8：实现 SemanticChunker
文件

rag/chunking/semantic_chunker.py

类

SemanticChunker(BaseChunker)

方法

chunk(parsed_doc: ParsedDocument) -> list[Chunk]

_compose_full_text(parsed_doc: ParsedDocument) -> str

_semantic_segment(full_text: str) -> list[str]

_map_segment_to_units(segments: list[str], raw_units: list[dict]) -> list[Chunk]

要求

第一版可先用规则 + TODO 占位，不强制调用 LLM

预留未来接入 LLM semantic split

验收标准

方法可跑通

有清晰 TODO 注释说明后续替换点

任务 2.9：实现 HybridChunker 与 ChunkPolicy
文件

rag/chunking/hybrid_chunker.py

rag/chunking/chunk_policy.py

类

HybridChunker

ChunkPolicy

方法

HybridChunker

chunk(parsed_doc: ParsedDocument) -> list[Chunk]

_rule_pre_split(parsed_doc: ParsedDocument) -> list[Chunk]

_semantic_refine(pre_chunks: list[Chunk]) -> list[Chunk]

_repair_chunk_boundaries(chunks: list[Chunk]) -> list[Chunk]

ChunkPolicy

resolve_policy(doc_type: str) -> dict

get_chunker(doc_type: str) -> BaseChunker

默认策略建议

SUBMISSION -> HybridChunker

GUIDELINE -> RuleChunker

REGULATION -> RuleChunker

CASE -> SemanticChunker

TEMPLATE -> RuleChunker

验收标准

传入 doc_type 可返回 chunker 实例

单测覆盖策略分派

3.3 Indexing 层
任务 2.10：实现 EmbeddingService
文件

rag/indexing/embedding_service.py

类

EmbeddingService

方法

embed_text(text: str) -> list[float]

batch_embed_texts(texts: list[str]) -> list[list[float]]

embed_chunks(chunks: list[Chunk]) -> list[dict]

health_check() -> bool

要求

封装现有 LLMClient.embed

批量模式优先

方法出错时抛出统一异常或返回明确信息

验收标准

能对文本/Chunk 生成向量

预留 provider 切换接口

任务 2.11：实现 MetadataEnricher
文件

rag/indexing/metadata_enricher.py

类

MetadataEnricher

方法

enrich_chunks(chunks: list[Chunk], parsed_doc: ParsedDocument) -> list[Chunk]

add_doc_level_metadata(chunks: list[Chunk], doc_meta: dict) -> list[Chunk]

normalize_retrieval_tags(chunks: list[Chunk]) -> list[Chunk]

要求

至少补充：

doc_title

doc_type

version

source_path

统一 metadata 结构

验收标准

enrich 后 chunk metadata 一致

任务 2.12：实现 DocSummaryBuilder
文件

rag/indexing/doc_summary_builder.py

类

DocSummaryBuilder

方法

build_doc_summary(parsed_doc: ParsedDocument, chunks: list[Chunk]) -> dict

build_section_summaries(chunks: list[Chunk]) -> list[dict]

extract_keywords(parsed_doc: ParsedDocument, chunks: list[Chunk]) -> list[str]

要求

第一版可以使用简单摘要策略

后续再接 LLM 摘要

保证接口稳定

验收标准

返回 doc_summary dict

至少包含 title/doc_type/chunk_count/keywords

任务 2.13：实现 IndexBuilder
文件

rag/indexing/index_builder.py

类

IndexBuilder

方法

build_index(parsed_doc: ParsedDocument, chunks: list[Chunk]) -> dict

_persist_chunks(chunks: list[Chunk]) -> None

_persist_vectors(chunk_vectors: list[dict]) -> None

_persist_doc_summary(doc_summary: dict) -> None

delete_doc_index(doc_id: str) -> None

rebuild_doc_index(doc_id: str) -> dict

要求

先做 repository 调用骨架

不在这里写复杂业务判断

预留事务边界

验收标准

方法签名与依赖清晰

可与 index pipeline 串起来

3.4 Retrieval 层
任务 2.14：实现 QueryRewriter
文件

rag/retrieval/query_rewriter.py

类

QueryRewriter

方法

rewrite(query: str, task_type: str | None = None) -> list[str]

expand_terms(query: str) -> list[str]

build_sub_queries(query: str, evidence_types: list[str]) -> list[str]

要求

第一版可基于规则实现

不强依赖 LLM

预留术语扩展位

验收标准

至少返回原 query + 简单扩展

任务 2.15：实现检索器骨架
文件

rag/retrieval/lexical_retriever.py

rag/retrieval/vector_retriever.py

rag/retrieval/hybrid_retriever.py

类

LexicalRetriever

VectorRetriever

HybridRetriever

方法

LexicalRetriever

search(query: str, filters: dict | None = None, top_k: int = 20) -> list[RetrievalHit]

VectorRetriever

search(query: str, filters: dict | None = None, top_k: int = 20) -> list[RetrievalHit]

search_by_embedding(query_embedding: list[float], filters: dict | None = None, top_k: int = 20) -> list[RetrievalHit]

HybridRetriever

retrieve(query: str, filters: dict | None = None, top_k: int = 20) -> list[RetrievalHit]

_merge_vector_and_lexical(vector_hits, lexical_hits) -> list[RetrievalHit]

要求

先把 repository 调用通路搭好

合并策略第一版简单即可

命中对象统一转 RetrievalHit

验收标准

HybridRetriever.retrieve() 可输出统一 hits

任务 2.16：实现 Reranker / ResultMerger / RelatedChunkExpander
文件

rag/retrieval/reranker.py

rag/retrieval/result_merger.py

rag/retrieval/related_chunk_expander.py

类与方法

Reranker

rerank(query: str, hits: list[RetrievalHit], top_k: int = 10) -> list[RetrievalHit]

score(query: str, text: str) -> float

batch_score(query: str, texts: list[str]) -> list[float]

ResultMerger

deduplicate(hits: list[RetrievalHit]) -> list[RetrievalHit]

merge_scores(hits: list[RetrievalHit]) -> list[RetrievalHit]

group_by_doc(hits: list[RetrievalHit]) -> list[dict]

RelatedChunkExpander

expand(hits: list[RetrievalHit], window_size: int = 1) -> list[RetrievalHit]

expand_same_section(hits: list[RetrievalHit]) -> list[RetrievalHit]

expand_doc_summary(hits: list[RetrievalHit]) -> list[dict]

要求

第一版先做规则/占位实现

重点先把依赖关系定住

验收标准

retriever → reranker → expander 串联可跑通

任务 2.17：实现 ContextBuilder
文件

rag/retrieval/context_builder.py

类

ContextBuilder

方法

build_context(query: str, hits: list[RetrievalHit], max_tokens: int) -> RetrievalContext

_select_hits_by_budget(hits: list[RetrievalHit], max_tokens: int) -> list[RetrievalHit]

_render_references(hits: list[RetrievalHit]) -> list[dict]

_build_evidence_blocks(hits: list[RetrievalHit]) -> list[dict]

要求

references 格式统一

保留 doc_id/chunk_id/page_span

超 token 预算时按优先级裁剪

验收标准

输出 RetrievalContext

含 references / grouped_docs / evidence_blocks

3.5 Pipeline 层
任务 2.18：实现 IndexPipeline
文件

rag/pipelines/index_pipeline.py

类

IndexPipeline

方法

run(file_path: str, doc_type: str, doc_meta: dict | None = None) -> dict

parse_document(file_path: str, doc_type: str) -> ParsedDocument

chunk_document(parsed_doc: ParsedDocument) -> list[Chunk]

embed_chunks(chunks: list[Chunk]) -> list[dict]

persist_index(parsed_doc: ParsedDocument, chunks: list[Chunk], vectors: list[dict]) -> dict

要求

作为知识入库主链路

依赖 parser registry + chunk policy + embedding service + index builder

每步记录日志

验收标准

单文件 build 流程可串通

任务 2.19：实现 RetrievePipeline
文件

rag/pipelines/retrieve_pipeline.py

类

RetrievePipeline

方法

run(query: str, filters: dict | None = None, top_k: int = 10, max_tokens: int = 4000) -> RetrievalContext

rewrite_query(query: str, task_type: str | None = None) -> list[str]

retrieve_hits(queries: list[str], filters: dict | None = None) -> list[RetrievalHit]

rerank_hits(query: str, hits: list[RetrievalHit]) -> list[RetrievalHit]

expand_hits(hits: list[RetrievalHit]) -> list[RetrievalHit]

build_context(query: str, hits: list[RetrievalHit], max_tokens: int) -> RetrievalContext

要求

作为对 Agent 和搜索接口统一提供的 retrieval 主链路

不耦合具体 API

验收标准

能独立被调用

返回 RetrievalContext

任务 2.20：实现基础 RAG 单测
文件

tests/rag/test_schema.py

tests/rag/test_parser_registry.py

tests/rag/test_chunk_policy.py

tests/rag/test_context_builder.py

要求

先用最小样例

保证公共模块稳定

4. 阶段 3：Agent 工作流重构
任务 3.1：实现 BaseAgent
文件

agents/base/base_agent.py

类

BaseAgent

方法

run(state: ReviewState) -> ReviewState

prepare_input(state: ReviewState) -> dict

invoke_llm(payload: dict) -> dict

parse_output(raw_output: str | dict) -> dict

validate_output(output: dict) -> dict

update_state(state: ReviewState, output: dict) -> ReviewState

要求

作为全部 Agent 的统一基类

默认方法里可抛 NotImplementedError

允许子类仅覆写局部方法

验收标准

可继承

具备统一接口

任务 3.2：实现 6 个角色 Agent 骨架
文件

agents/roles/planner_agent.py

agents/roles/retriever_agent.py

agents/roles/reviewer_agent.py

agents/roles/reflector_agent.py

agents/roles/synthesizer_agent.py

agents/roles/qc_agent.py

PlannerAgent

方法：

run(state: ReviewState) -> ReviewState

prepare_input(state: ReviewState) -> dict

build_checklist(section_text: str, review_type: str) -> list[dict]

select_evidence_types(checklist: list[dict]) -> list[str]

update_state(state, output) -> ReviewState

要求：

第一版可用规则生成 checklist

输出写入 state.task_plan

RetrieverAgent

方法：

run(state: ReviewState) -> ReviewState

build_queries(state: ReviewState) -> list[str]

select_filters(state: ReviewState) -> dict

call_retrieve_pipeline(queries: list[str], filters: dict) -> RetrievalContext

update_state(state, output) -> ReviewState

要求：

依赖 RetrievePipeline

结果写入 state.retrieval_context

ReviewerAgent

方法：

run(state: ReviewState) -> ReviewState

prepare_input(state: ReviewState) -> dict

generate_findings(state: ReviewState) -> dict

bind_references(findings: dict, references: list[dict]) -> dict

update_state(state, output) -> ReviewState

要求：

输出结构化 findings/risks/recommendations

先写骨架，不追求最终 Prompt 效果

ReflectorAgent

方法：

run(state: ReviewState) -> ReviewState

check_missing_items(state: ReviewState) -> list[dict]

check_evidence_sufficiency(state: ReviewState) -> list[dict]

check_reasoning_consistency(state: ReviewState) -> list[dict]

update_state(state, output) -> ReviewState

要求：

第一版可基于规则检查

结果写入 reflection_notes

SynthesizerAgent

方法：

run(state: ReviewState) -> ReviewState

normalize_review_output(state: ReviewState) -> dict

render_standard_conclusion(state: ReviewState) -> dict

attach_final_references(state: ReviewState) -> list[dict]

update_state(state, output) -> ReviewState

要求：

输出标准章节结论结构

不直接写数据库

QCAgent

方法：

run(state: ReviewState) -> ReviewState

check_reference_completeness(state: ReviewState) -> list[dict]

check_overclaiming(state: ReviewState) -> list[dict]

check_format_compliance(state: ReviewState) -> list[dict]

check_conflicts(state: ReviewState) -> list[dict]

update_state(state, output) -> ReviewState

要求：

明确把 QC 从 reviewer 中拆出来

任务 3.3：实现 ReviewWorkflow
文件

agents/review/review_workflow.py

类

ReviewWorkflow

方法

run(state: ReviewState) -> ReviewState

run_planner(state: ReviewState) -> ReviewState

run_retriever(state: ReviewState) -> ReviewState

run_reviewer(state: ReviewState) -> ReviewState

run_reflector(state: ReviewState) -> ReviewState

run_synthesizer(state: ReviewState) -> ReviewState

run_qc(state: ReviewState) -> ReviewState

should_retry_retrieval(state: ReviewState) -> bool

should_revise_review(state: ReviewState) -> bool

要求

串联 6 个角色

第一版流程固定即可

预留重试钩子，但先不实现复杂策略

验收标准

能基于 mock state 跑完完整工作流

任务 3.4：实现 SectionReviewExecutor
文件

agents/review/section_review_executor.py

类

SectionReviewExecutor

方法

execute(section_payload: dict, run_config: dict) -> ReviewState

build_initial_state(section_payload: dict, run_config: dict) -> ReviewState

persist_section_result(state: ReviewState) -> None

要求

用于单章节执行

persist 先预留 repository 调用

不把复杂逻辑塞进 controller

验收标准

可执行单章节 mock 审评

任务 3.5：实现 MultiRoleOrchestrator
文件

agents/review/multi_role_orchestrator.py

类

MultiRoleOrchestrator

方法

run_sections(section_list: list[dict], run_config: dict) -> list[ReviewState]

run_single_section(section_payload: dict, run_config: dict) -> ReviewState

merge_section_results(states: list[ReviewState]) -> dict

build_run_summary(states: list[ReviewState]) -> dict

要求

支持串行执行即可，先不强行并发

预留后续并发扩展

验收标准

可对多个章节顺序执行并汇总

任务 3.6：实现 PromptManager 骨架
文件

agents/prompts/prompt_manager.py

类

PromptManager

方法

load_template(template_name: str) -> str

render(template_name: str, payload: dict) -> str

list_templates(prefix: str | None = None) -> list[str]

要求

兼容现有 .j2

第一版不改模板内容，只提供统一入口

任务 3.7：Agent 单测
文件

tests/agents/test_review_state.py

tests/agents/test_workflow.py

要求

至少验证 workflow 主链可跑通

用 mock retriever / mock llm

5. 阶段 4：反馈闭环与评测
任务 4.1：实现反馈采集模块
文件

feedback/collection/feedback_validator.py

feedback/collection/feedback_ingestor.py

feedback/collection/diff_extractor.py

FeedbackValidator

方法：

validate(feedback_payload: dict) -> None

validate_labels(labels: list[str]) -> None

validate_revised_output(revised_output: dict | str) -> None

FeedbackIngestor

方法：

ingest(feedback_payload: dict) -> dict

normalize_feedback(feedback_payload: dict) -> dict

attach_run_context(feedback_payload: dict) -> dict

persist_feedback(feedback_record: dict) -> str

DiffExtractor

方法：

extract_diff(original_output: str, revised_output: str) -> dict

extract_structured_diff(original: dict, revised: dict) -> dict

classify_diff(diff_result: dict) -> list[str]

验收标准

接受最小 feedback payload

能输出标准化 feedback record

任务 4.2：实现错误归因模块
文件

feedback/attribution/root_cause_classifier.py

feedback/attribution/severity_scorer.py

feedback/attribution/feedback_router.py

方法

RootCauseClassifier

classify(feedback_record: dict, run_trace: dict) -> dict

classify_rag_issue(feedback_record: dict, run_trace: dict) -> str | None

classify_agent_issue(feedback_record: dict, run_trace: dict) -> str | None

classify_prompt_issue(feedback_record: dict, run_trace: dict) -> str | None

classify_rule_issue(feedback_record: dict, run_trace: dict) -> str | None

SeverityScorer

score(feedback_record: dict, root_cause: dict) -> dict

is_high_risk(feedback_record: dict) -> bool

FeedbackRouter

route(feedback_record: dict, root_cause: dict) -> list[str]

要求

第一版使用规则映射即可

路由类型：

rule_fix

prompt_fix

retrieval_fix

rerank_dataset

preference_dataset

regression_case

验收标准

输入 feedback 可得到 root cause + severity + routes

任务 4.3：实现优化资产构建器
文件

feedback/optimization/rule_task_builder.py

feedback/optimization/prompt_task_builder.py

feedback/optimization/retrieval_task_builder.py

feedback/optimization/rerank_dataset_builder.py

feedback/optimization/preference_dataset_builder.py

feedback/optimization/regression_case_builder.py

要求

RuleTaskBuilder

build(feedback_record: dict, root_cause: dict) -> dict

extract_candidate_rule(feedback_record: dict) -> dict

persist_rule_ticket(ticket: dict) -> str

PromptTaskBuilder

build(feedback_record: dict, root_cause: dict) -> dict

suggest_prompt_patch(feedback_record: dict) -> dict

persist_prompt_ticket(ticket: dict) -> str

RetrievalTaskBuilder

build(feedback_record: dict, root_cause: dict) -> dict

build_missing_evidence_case(feedback_record: dict) -> dict

persist_retrieval_ticket(ticket: dict) -> str

RerankDatasetBuilder

build_pairwise_sample(feedback_record: dict, run_trace: dict) -> dict

append_sample(sample: dict) -> None

PreferenceDatasetBuilder

build_preference_sample(original_output: dict, revised_output: dict, feedback_record: dict) -> dict

append_sample(sample: dict) -> None

RegressionCaseBuilder

build_case(feedback_record: dict, run_trace: dict) -> dict

append_case(case_data: dict) -> None

验收标准

至少能生成 dict 形式优化资产

append/persist 接口清晰

任务 4.4：实现评测与回放模块
文件

feedback/evaluation/replay_runner.py

feedback/evaluation/metrics_calculator.py

feedback/evaluation/blind_review_builder.py

feedback/evaluation/report_generator.py

方法

ReplayRunner

run_case(case_id: str, version_config: dict) -> dict

run_batch(case_ids: list[str], version_config: dict) -> list[dict]

compare_versions(case_ids: list[str], old_version: dict, new_version: dict) -> dict

MetricsCalculator

calc_retrieval_metrics(results: list[dict]) -> dict

calc_review_metrics(results: list[dict]) -> dict

calc_feedback_metrics(feedback_records: list[dict]) -> dict

calc_version_gain(old_results: list[dict], new_results: list[dict]) -> dict

BlindReviewBuilder

build_blind_review_packets(case_results: list[dict]) -> list[dict]

ReportGenerator

generate_evaluation_report(metrics: dict, compare_result: dict) -> dict

render_markdown_report(report_data: dict) -> str

验收标准

能基于 mock cases 产生 report 数据

任务 4.5：实现 FeedbackClosedLoopPipeline
文件

feedback/pipelines/feedback_closed_loop_pipeline.py

类

FeedbackClosedLoopPipeline

方法

run(feedback_payload: dict) -> dict

ingest_feedback(feedback_payload: dict) -> dict

classify_root_cause(feedback_record: dict) -> dict

route_feedback(feedback_record: dict, root_cause: dict) -> list[str]

build_optimization_assets(feedback_record: dict, root_cause: dict, routes: list[str]) -> dict

trigger_regression_update(feedback_record: dict, root_cause: dict) -> None

要求

串起 collection / attribution / optimization

先做同步链路

每一步输出清晰日志

验收标准

一条 feedback payload 可完整走完闭环

任务 4.6：反馈单测
文件

tests/feedback/test_diff_extractor.py

tests/feedback/test_root_cause_classifier.py

tests/feedback/test_feedback_pipeline.py

6. Application Service 与 API 编排
任务 5.1：实现 Application Service 骨架
文件

application/knowledge_app_service.py

application/retrieval_app_service.py

application/pre_review_app_service.py

application/feedback_app_service.py

方法要求

KnowledgeAppService

upload_knowledge(files: list, meta: dict) -> dict

submit_parse(doc_id: str) -> dict

query_knowledge(filters: dict) -> dict

delete_knowledge(doc_id: str) -> dict

rebuild_index(doc_id: str) -> dict

get_parse_progress(task_id: str) -> dict

RetrievalAppService

semantic_search(query: str, filters: dict, top_k: int) -> dict

build_review_context(query: str, review_type: str, filters: dict) -> dict

debug_retrieval(query: str, filters: dict) -> dict

PreReviewAppService

create_project(payload: dict) -> dict

upload_submission(project_id: str, files: list) -> dict

parse_submission(submission_id: str) -> dict

run_pre_review(project_id: str, submission_id: str, run_config: dict) -> dict

get_run_result(run_id: str) -> dict

get_section_traces(run_id: str, section_id: str) -> dict

export_report(run_id: str) -> dict

FeedbackAppService

submit_feedback(payload: dict) -> dict

get_feedback_stats(filters: dict) -> dict

replay_cases(case_ids: list[str], version_config: dict) -> dict

generate_regression_cases(filters: dict) -> dict

要求

先做编排，不深写 repository

可以适配旧 controller/service

任务 5.2：新增 API router 骨架
文件

api/routers/retrieval_router.py

api/routers/feedback_router.py

要求

先只创建最小接口：

retrieval_router.py

POST /retrieval/search

POST /retrieval/context

feedback_router.py

POST /feedback/submit

GET /feedback/stats

POST /feedback/replay

验收标准

路由可注册

返回 mock 或骨架数据

7. CLI 脚本任务
任务 6.1：实现索引构建脚本骨架
文件

scripts/build_knowledge_index.py

方法

parse_args()

load_input_files(input_dir: str, file_patterns: list[str]) -> list[str]

build_single_file(file_path: str, doc_type: str, force: bool = False) -> dict

build_batch(file_paths: list[str], doc_type: str) -> list[dict]

main()

验收标准

python scripts/build_knowledge_index.py --help 可运行

任务 6.2：实现检索评测脚本骨架
文件

scripts/evaluate_retrieval.py

方法

parse_args()

load_eval_cases(case_file: str) -> list[dict]

run_single_case(case_data: dict) -> dict

run_eval(cases: list[dict]) -> list[dict]

calc_metrics(results: list[dict]) -> dict

main()

任务 6.3：实现反馈回放脚本骨架
文件

scripts/replay_feedback_cases.py

方法

parse_args()

load_cases(case_source: str) -> list[dict]

replay_case(case_data: dict, version_config: dict) -> dict

compare_runs(old_result: dict, new_result: dict) -> dict

main()

任务 6.4：实现回归案例生成脚本骨架
文件

scripts/generate_regression_cases.py

方法

parse_args()

load_feedback_records(filters: dict) -> list[dict]

build_case_from_feedback(feedback_record: dict) -> dict

save_cases(case_list: list[dict], output_file: str) -> None

main()

8. 仓储层与兼容要求
任务 7.1：Repository 骨架
文件

infrastructure/repositories/file_repository.py

infrastructure/repositories/knowledge_repository.py

infrastructure/repositories/review_repository.py

infrastructure/repositories/feedback_repository.py

infrastructure/repositories/evaluation_repository.py

要求

先定义接口类或最小实现，方法名与上层应用匹配。

例如 feedback_repository.py：

save_feedback(record: dict) -> str

get_feedback_by_id(feedback_id: str) -> dict | None

list_feedback(filters: dict) -> list[dict]

说明

这里先做适配层，不要求立即完全替换原 ORM。

任务 7.2：兼容旧服务的适配策略
要求

Codex 在新代码中加入清晰注释：

哪些地方复用旧 services/*

哪些地方复用旧 utils/parser/*

哪些地方复用旧 memory/rag/pipeline.py

哪些地方暂时保留旧 controller

验收标准

文档或代码注释中写明兼容点

不做“推倒重来”式重构

9. 文档任务
任务 8.1：新增设计文档骨架
文件

docs/rag_design.md

docs/agent_design.md

docs/feedback_design.md

docs/api_contract.md

要求

每个文档至少包含：

模块职责

类图/调用链说明（文字即可）

输入输出定义

已实现 / 待实现项

10. 最低验收清单

Codex 本轮开发完成后，最低要满足以下条件：

10.1 结构验收

新目录创建完成

核心 schema 完成

核心类和方法骨架完成

10.2 RAG 验收

IndexPipeline.run() 可跑通最小流程

RetrievePipeline.run() 可返回 RetrievalContext

10.3 Agent 验收

ReviewWorkflow.run() 可用 mock 数据跑通

10.4 Feedback 验收

FeedbackClosedLoopPipeline.run() 可处理一条 mock feedback

10.5 脚本验收

所有 scripts/*.py 有 CLI 帮助信息

可运行到参数解析层

10.6 单测验收

至少新增：

schema 单测

parser registry 单测

workflow 单测

feedback pipeline 单测

11. 建议 Codex 的输出顺序

为了降低失败率，要求 Codex 严格按下面顺序开发：

创建目录和 __init__.py

创建 enums 和 schema

创建 parser / chunker 抽象基类

创建 retrieval schema 与 pipeline 骨架

创建 agent base 与 review state

创建 workflow 与角色 agent 骨架

创建 feedback schema 与 pipeline 骨架

创建 application service 骨架

创建 scripts 骨架

补测试与 docs

12. 建议写给 Codex 的额外约束文本

你可以直接把下面这段附给 Codex：

请优先生成“可运行骨架”，而不是追求一次性实现完整业务逻辑。
所有核心对象必须使用 dataclass 或等价强类型结构。
所有方法必须保留 docstring。
所有 pipeline、agent、feedback 主方法必须预留日志。
对暂未实现的复杂逻辑，请使用清晰的 TODO 注释说明，而不是省略方法。
保持新代码与旧原型可并存，不要直接删除旧模块。
优先保证接口稳定、结构清晰、可测试。