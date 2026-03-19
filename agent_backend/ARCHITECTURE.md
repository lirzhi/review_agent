# Agent Backend 架构视图

本文档针对 `agent/agent_backend` 的后端代码结构，给出：
- 目录结构（聚焦代码）
- 每个核心文件的方法清单
- 方法主要职责说明

说明：
- 资源文件（大量 `script/指导原则/*.pdf`）不在此清单内。
- 模板文件（`.j2`）仅按用途说明，不逐行展开。

## 1. 目录结构（代码视图）

```text
agent_backend/
├─ app.py
├─ config/
│  ├─ settings.py
│  └─ mapping.json / redis.conf
├─ controller/
│  ├─ __init__.py
│  ├─ file_controller.py
│  ├─ knowledge_controller.py
│  ├─ pre_review_controller.py
│  ├─ qa_controller.py
│  └─ rl_controller.py
├─ services/
│  ├─ file_service.py
│  ├─ knowledge_service.py
│  └─ pre_review_service.py
├─ memory/
│  ├─ base.py / memory_manager.py / embedding.py
│  ├─ rag/
│  │  ├─ document.py
│  │  └─ pipeline.py
│  ├─ storage/
│  │  ├─ vector_store.py
│  │  └─ neo4j_store.py
│  └─ types/
│     ├─ working.py / episodic.py / semantic.py / perceptual.py / long_term.py
├─ agents/
│  ├─ agent_compile.py
│  ├─ knowledge_index_agent.py
│  ├─ pre_review_agent/
│  │  ├─ pre_review_state.py
│  │  ├─ pre_review.py
│  │  └─ pre_review_agent.py
│  └─ multi_agent/
│     ├─ roles.py
│     ├─ prompt_manager.py
│     └─ workflow.py
├─ llm/
│  ├─ base.py
│  ├─ model_setting.py
│  ├─ factory.py
│  ├─ client.py
│  ├─ llm_server.py
│  └─ providers/
│     ├─ glm_models.py
│     ├─ local_models.py
│     └─ openai_compatible.py
├─ database/
│  ├─ __init__.py
│  ├─ doc_store_conn.py
│  ├─ mysql/
│  │  ├─ db_model.py
│  │  └─ mysql_conn.py
│  ├─ redis/redis_conn.py
│  ├─ es/es_conn.py
│  └─ vector/
│     ├─ vector_manager.py
│     └─ milvus_db.py
├─ utils/
│  ├─ common_util.py
│  ├─ file_util.py
│  ├─ text_util.py
│  ├─ method_trace.py
│  └─ parser/
│     ├─ parser_manager.py
│     ├─ pdf_parser.py
│     ├─ docx_parser.py
│     ├─ material_parser.py
│     └─ submission_material_parser.py
├─ context/builder.py
├─ common_tools/builtin/ (memory_tool/rag_tool/note_tool/terminal_tool)
├─ prompts/ (系统提示词 + 预审提示词 + 知识解析提示词)
├─ agentic_rl/ (adapter, reward, training, eval)
├─ evaluate/ (人工与LLM评估)
├─ script/ (离线解析/上传脚本)
└─ test/ (接口联调与OCR测试脚本)
```

## 2. 启动与路由层

### `app.py`
- `_is_port_open(host, port, timeout)`: 检测端口是否可连接。
- `_should_boot_llm()`: 判断是否自动启动 LLM 子服务（含 debug/reloader 处理）。
- `_boot_llm_server()`: 通过 `uvicorn` 启动 `llm_server`。
- `create_app()`: 创建 Flask app、注册控制器、注入 keep-alive 响应头。

### `controller/__init__.py`
- `register_controllers(app)`: 汇总注册各 Blueprint。

### `controller/file_controller.py`
- `get_file_service()`: 懒加载 `FileService` 单例。
- `health()`: 健康检查。
- `upload_file()`: 普通文件上传（单/多文件）。
- `add_file()`: 以路径导入文件。
- `list_files()`: 按条件分页查文件。
- `get_file(doc_id)`: 文件详情。
- `update_file(doc_id)`: 更新文件元信息。
- `delete_file(doc_id)`: 删除文件。
- `update_chunk_status(doc_id)`: 更新分块状态。
- `update_review_status(doc_id)`: 更新审评状态。
- `parse_file(doc_id)`: 同步解析并落盘到 `data/parsed`。

### `controller/knowledge_controller.py`
- `get_knowledge_service()`: 懒加载 `KnowledgeService`。
- `upload_knowledge()`: 上传知识文件并异步触发解析。
- `update_knowledge(doc_id)`: 更新知识条目。
- `delete_knowledge(doc_id)`: 删除知识条目及索引。
- `query_knowledge()`: 条件查询知识库。
- `semantic_query()`: 语义检索（支持 `min_score`）。
- `parse_progress()`: 查询解析任务进度。
- `parse_knowledge(doc_id)`: 手动触发解析任务。
- `parse_progress_stream()`: SSE 流式推送解析进度。

### `controller/pre_review_controller.py`
- `get_pre_review_service()`: 懒加载 `PreReviewService`。
- `create_project()/delete_project()/list_projects()/project_detail()`: 项目管理。
- `upload_submission()/list_submissions()`: 申报资料管理。
- `submission_content()/submission_sections()/submission_preview()`: 原文与结构查看。
- `run_pre_review()/run_history()`: 发起预审与历史查询。
- `dashboard_summary()/agent_roles()`: 看板与角色信息。
- `get_sections()/get_sections_overview()/get_traces()`: 章节结论与轨迹查询。
- `export_report()`: 导出报告。
- `add_feedback()/feedback_stats()`: 反馈写入与统计。

### `controller/qa_controller.py`
- `get_knowledge_service()`: 获取知识服务。
- `health()`: 健康检查。
- `ask()`: 面向知识库的问答接口。

### `controller/rl_controller.py`
- `health()`: 健康检查。
- `calc_feedback_metrics()`: 反馈指标计算接口。
- `evaluate_predictions()`: 预测质量评估接口。

## 3. 服务层

### `services/file_service.py` (`FileService`)
- `_now_str()/_to_dict()/_build_doc_id()/_display_name()/_storage_name()`: 文件元信息与命名工具。
- `get_file_by_doc_id()`: 根据 doc_id 查详情。
- `upload_file()/add_file()`: 上传或路径导入。
- `update_file()/delete_file()`: 更新与软删（含物理文件处理）。
- `_paginate()`: 分页工具。
- `query_by_file_name()/query_by_doc_id()/query_by_classification()`: 多维查询。
- `update_chunk_status()/update_review_status()`: 分块/审评状态写入。

### `services/knowledge_service.py` (`KnowledgeService`)
- `rag`(property): 获取 `RAGPipeline`。
- `_run_async_parse()/_submit_async_parse()`: 异步解析任务执行与提交。
- `_set_parse_progress()/get_parse_progress()/ _cleanup_parse_progress_locked()`: 解析进度管理。
- `_mark_chunk_status_from_saved()`: 从解析结果回写分块状态。
- `upload_knowledge()`: 上传后自动提交异步解析。
- `update_knowledge()/delete_knowledge()`: 知识更新/删除。
- `query_knowledge()`: 条件+关键字查询（含解析进度聚合）。
- `_ensure_index_for_query()`: 基于已解析文件补建向量索引。
- `semantic_query()`: 语义检索并按文档聚合结果。
- `submit_parse(doc_id)`: 手动提交解析任务。

### `services/pre_review_service.py` (`PreReviewService`)
主要职责（文件较大）：
- 项目生命周期管理（创建、删除、列表、详情）。
- 申报资料上传、章节结构解析、原文预览。
- 运行预审工作流（按章节调用 agent）。
- 写入章节结论、trace、反馈及准确率统计。
- 报告导出与历史审计查询。

## 4. RAG 与记忆层

### `memory/rag/document.py` (`DocumentProcessor`)
- `_normalize_text()/ _sentence_split()`: 文本归一化与句子切分。
- `_split_long_text()`: 超长文本规则切分。
- `_normalize_raw_units()`: 解析器输出规范化。
- `_compose_full_text()`: 合并为整篇文本并记录 span 映射。
- `_llm_chunk_once()`: 单次 LLM 语义分段。
- `_semantic_chunk_full_text()`: 文档级分段（超长时窗口化）。
- `_is_valid_segments()/ _merge_small_segments()`: 分段质量校验与合并。
- `_segment_meta_by_ratio()`: 将分段结果映射回页码/来源 chunk。
- `process(file_path, file_type)`: 完整“解析->整文分段->带元数据 chunk”流程。

### `memory/rag/pipeline.py` (`RAGPipeline`)
- `index_file()`: 解析、chunk enrich、embedding、入向量库、生成文档摘要索引。
- `index_preparsed()`: 从已解析结果重建向量索引。
- `retrieve()`: 向量召回 + rerank + lexical 混合打分。
- `build_context()`: 组装最终上下文（含 references）。
- 内部工具：
  - `_query_terms()/ _lexical_score()`
  - `_parse_chunk_order()`
  - `_doc_related_chunks()`: 同文档相关片段回补。
  - `_doc_summary_meta()`: 读取文档摘要索引。

### `memory/embedding.py` (`EmbeddingService`)
- 统一 embedding 入口（调用 `LLMClient.embed`）。

### `memory/base.py`
- `MemoryItem`: 记忆条目结构。
- `MemoryConfig`: 记忆配置。
- `BaseMemory`: 记忆接口抽象基类。

### `memory/memory_manager.py` (`MemoryManager`)
- 协调 working/episodic/semantic/perceptual/long-term 记忆读写。

### `memory/types/*.py`
- `WorkingMemory`: 短期工作记忆（TTL）。
- `EpisodicMemory`: 事件序列记忆。
- `SemanticMemory`: 语义知识记忆。
- `PerceptualMemory`: 感知类记忆。
- `LongTermMemory`: 长期记忆持久化抽象。

### `memory/storage/vector_store.py` (`VectorStore`)
- `add()/search()/list_by_doc()/delete_by_doc()`：向量存储统一接口。

### `memory/storage/neo4j_store.py` (`Neo4jStore`)
- 图存储占位实现（知识图谱扩展点）。

## 5. Agent 层

### `agents/knowledge_index_agent.py` (`KnowledgeIndexAgent`)
- `analyze_chunk(text)`: 片段摘要+关键词抽取。
- `analyze_document(title, chunks)`: 文档级摘要+关键词抽取。

### `agents/pre_review_agent/pre_review_state.py`
- `PreReviewState`: 预审状态对象（章节、规则、证据、结论等）。

### `agents/pre_review_agent/pre_review.py` (`PreReviewNodes`)
- 预审图节点方法集合（检索、审查、反思、汇总等）。

### `agents/pre_review_agent/pre_review_agent.py` (`PreReviewAgent`)
- 构建/执行预审图。
- `build_pre_review_agent(...)`: 组装带 memory/context 的 agent。

### `agents/multi_agent/roles.py`
- `AgentRole`: 角色定义（名称、职责、输入输出约束）。
- `build_default_roles()`: 默认多角色集合。

### `agents/multi_agent/prompt_manager.py` (`PromptManager`)
- 统一角色提示词渲染管理。

### `agents/multi_agent/workflow.py` (`MultiAgentPreReviewWorkflow`)
- 多 Agent 协作状态机/图执行器。

### `agents/agent_compile.py`
- `compile_agents()`: 汇总编译可用 agent。

## 6. LLM 层

### `llm/base.py`
- `ChatModelBase / ParseModelBase / EmbeddingModelBase / RerankModelBase`: 四类模型统一基类。

### `llm/model_setting.py`
- `_resolve_key_path()`: 密钥路径解析。
- `get_active_model_name(task)`: 按任务选择当前模型。
- `get_model_conf(name)`: 取模型配置。

### `llm/factory.py` (`ModelFactory`)
- `chat_model()/parse_model()/embedding_model()/rerank_model()`: 按配置创建模型实例。
- `_Null*`：兜底空实现。

### `llm/client.py` (`LLMClient`)
- `chat()/parse()/parse_layout()`: 生成与解析调用统一入口。
- `embed()/batch_embed()`: 向量调用。
- `rerank()`: 重排序调用。
- `extract_json(raw_text)`: 从模型输出中提取 JSON。

### `llm/providers/glm_models.py`
- `GLMOCRParseModel`: GLM-OCR 解析模型实现。
- `GLMEmbeddingModel`: GLM embedding 实现。
- `GLMRerankModel`: GLM rerank 实现。

### `llm/providers/openai_compatible.py`
- `OpenAICompatibleTextModel`: OpenAI 兼容 chat/parse 模型实现。

### `llm/providers/local_models.py`
- `HashEmbeddingModel` / `OpenAICompatibleEmbeddingModel`
- `LexicalRerankModel` / `HashRerankModel`

### `llm/llm_server.py`
- FastAPI 服务暴露 chat/parse/embed/rerank 接口与健康检查。

## 7. 数据与存储层

### `database/mysql/db_model.py`
核心 ORM 表：
- `FileInfo`：知识库文件
- `PreReviewProject`：预审项目
- `PreReviewSubmissionFile`：申报资料文件
- `PreReviewRun`：预审运行记录
- `PreReviewSectionConclusion`：章节结论
- `PreReviewSectionTrace`：章节 trace
- `PreReviewFeedback`：人工反馈
- 以及 `RequireInfo/ReportContent/PharmacyInfo/QAInfo/KnowledgeTag/KnowledgeFileTag`

### `database/mysql/mysql_conn.py` (`MysqlConnection`)
- 连接创建、未知数据库自动创建、Session 管理。

### `database/vector/vector_manager.py`
- `cosine_similarity()`
- `VectorManager`: 轻量向量管理器。

### `database/vector/milvus_db.py`
- `MilvusDB`: Milvus 封装。

### `database/redis/redis_conn.py`
- `RedisMsg`, `Payload`, `RedisDB`: Redis 消息/缓存封装。

### `database/es/es_conn.py`
- `ESConnection`: Elasticsearch 文档检索连接实现。

### `database/doc_store_conn.py`
- 文档存储检索抽象接口（匹配表达式、融合表达式等）。

## 8. 解析器与工具

### `utils/parser/parser_manager.py` (`ParserManager`)
- `register_parser()/list_supported_extensions()/is_supported()/get_parser()/parse()`

### `utils/parser/pdf_parser.py`
- `_chunk_text()`: 页内初步切块。
- `parse_pdf()`: PDF 抽取为 chunk 列表。

### `utils/parser/docx_parser.py`
- `parse_docx()`: DOCX 段落解析。

### `utils/parser/material_parser.py`
- `parse_material()`: txt/md 等纯文本解析。

### `utils/parser/submission_material_parser.py`
核心方法：
- `_extract_pages()`：提取页文本
- `_parse_toc_entries()`：目录识别
- `_extract_heading_hits()`：章节标题识别
- `_slice_section_content()`：章节正文切片
- `_build_section_tree()/ _build_chapter_structure_from_sections()`
- `_annotate_sections_and_aggregate_leaf_siblings()`
- `_build_review_units()`
- `parse_submission_material()`：输出结构化申报资料

### 其他工具
- `utils/common_util.py`: `ResponseMessage`、并行装饰器
- `utils/file_util.py`: 路径、配置加载、文件类型、目录工具
- `utils/text_util.py`: 文本清洗、分块、token 估算
- `utils/method_trace.py`: 方法调用追踪（调试）
- `context/builder.py`: GSSC 上下文构建（Gather/Select/Structure/Compress）

## 9. 提示词与脚本

### `prompts/`
- `pre_review_agent_prompt/*.j2`: planner/retriever/reviewer/reflector/synthesizer
- `knowledge_parse_agent_prompt/*.j2`: 分块、摘要、JSON 输出约束
- `template_manager.py`: Jinja2 模板渲染器

### `script/`
- `parse_pdf_for_kb.py`: 知识 PDF 离线解析实验脚本
- `parse_submission_material.py`: 申报资料离线解析实验脚本
- `upload_guidelines_to_kb.py`: 批量调用上传接口脚本

### `test/`
- `run_parse_api_test.py`: 上传+解析+进度轮询联调
- `glm-ocr_test_print.py`: GLM-OCR 简化测试

---

## 10. 主调用链（按业务）

### A. 知识库上传与异步解析
1. `knowledge_controller.upload_knowledge`
2. `knowledge_service.upload_knowledge`
3. `knowledge_service._submit_async_parse`
4. `rag.pipeline.index_file`
5. `memory.rag.document.process`（整文 LLM 分段）
6. `vector_store.add` 建立 chunk/doc_summary 索引
7. `knowledge_controller.parse_progress(_stream)` 查询或流式推送进度

### B. 语义检索
1. `knowledge_controller.semantic_query`
2. `knowledge_service.semantic_query`
3. `rag.pipeline.build_context -> retrieve`
4. 返回 `grouped_docs + matched_hits + related_chunks`

### C. 按章节预审
1. `pre_review_controller.run_pre_review`
2. `pre_review_service` 加载 submission 章节
3. `pre_review_agent/multi_agent workflow` 按章节循环审查
4. 结果入库：`PreReviewRun/SectionConclusion/SectionTrace`
5. `get_sections/get_traces/export_report` 查询与导出

