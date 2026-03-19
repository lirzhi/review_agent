# System Review And Iteration Plan

## 1. Current End-to-End Flow

### 1.1 Knowledge Ingestion
1. `KnowledgeService.upload_knowledge()` accepts files and persists metadata through `FileService`.
2. `KnowledgeService._submit_async_parse()` schedules parsing and indexing.
3. `RAGPipeline.index_file()` executes:
   - parse full text
   - semantic chunking
   - chunk summary/keywords extraction via `KnowledgeIndexAgent`
   - document summary extraction
   - embedding and vector storage
   - parsed artifact persistence under `data/parsed/<doc_id>.json`
4. `KnowledgeService.semantic_query()` serves retrieval for downstream review.

### 1.2 Submission And Pre-review
1. `PreReviewService.upload_submission()` stores submission files and, for CTD projects, binds them to section nodes.
2. `PreReviewService._build_structured_project_payload()` merges:
   - CTD/raw-data section catalog
   - uploaded files
   - manual concern points
   - edited content
3. `PreReviewService.run_pre_review()` seeds memory and iterates section-by-section.
4. `_review_single_chunk()` performs:
   - section query build
   - knowledge retrieval
   - section packet build
   - agent orchestration
   - findings normalization and paragraph-anchor binding
   - section conclusion / trace persistence

### 1.3 Multi-agent Review Workflow
Current orchestrator: `MultiAgentPreReviewWorkflow`
- `planner`: decides review steps and focus
- `retriever`: filters evidence
- `reviewer`: drafts issues
- `reflector`: removes weak or duplicated issues
- `synthesizer`: outputs final conclusion and score

### 1.4 Feedback Closed Loop
1. `FeedbackAppService.submit_feedback()` enters `FeedbackClosedLoopPipeline`.
2. Pipeline stages:
   - `FeedbackIngestor`
   - `RootCauseClassifier`
   - `FeedbackRouter`
   - optimization asset builders
   - regression case builder
3. Existing implementation already stored assets and cases, but prompt-fix was mostly a placeholder before this round.

### 1.5 Replay / Evaluation
1. `ReplayRunner.run_case()` loads saved case.
2. It invokes either full pre-review or section replay.
3. `version_config.run_config` is the extension point for iterative optimization.

## 2. Main Structural Problems Found

### 2.1 Prompt layer was not trustworthy
- `pre_review_agent_prompt/*.j2` contained severe mojibake and weak constraints.
- `workflow.py` also contained mojibake in system messages, fallback steps, and fallback findings.
- This made agent behavior unstable even when the rest of the pipeline was structurally complete.

### 2.2 Prompt optimization was not executable
- `PromptTaskBuilder` previously only returned a minimal ticket-like payload.
- No prompt bundle was produced.
- No prompt version could be replayed through `version_config`.

### 2.3 Closed loop existed conceptually but not operationally
- The project already had ingestion, attribution, routing, assets, regression cases, and replay.
- But the loop from feedback to prompt change to replay verification was not actually connected.

## 3. First Real Iteration Implemented

### 3.1 Clean prompt templates
Rewrote these templates to explicit, constrained versions:
- `planner.j2`
- `retriever.j2`
- `reviewer.j2`
- `reflector.j2`
- `synthesizer.j2`

### 3.2 Prompt override mechanism
`PromptManager.render()` now supports per-run prompt bundles:
- inline bundle dict
- bundle path on disk
- full template override
- template suffix patch

This keeps the base prompts stable while allowing replay to inject optimization patches safely.

### 3.3 Workflow upgraded to consume prompt bundles
`MultiAgentPreReviewWorkflow` now:
- reads `prompt_config` from state
- renders templates with dynamic prompt patches
- records `prompt_version_id` and `prompt_bundle_path` into trace summary
- uses clean system prompts and fallback logic

### 3.4 Pre-review service now propagates run_config to section packets
This makes prompt-version replay possible for both:
- full run
- section replay

### 3.5 Prompt optimization assets are now executable
`PromptTaskBuilder` now generates:
- target templates
- diagnosis
- optimization actions
- template suffix patches
- prompt bundle payload
- replay-ready `version_config`

### 3.6 Asset persistence now writes prompt bundle files
`FeedbackClosedLoopPipeline.persist_assets()` now persists:
- bundle json
- prompt bundle json under `feedback_assets/prompt_versions/`
- replay-ready prompt configuration inside prompt_fix asset

## 4. What This Enables Now

A real minimal self-iteration path now exists:
1. expert feedback enters the closed loop
2. root cause is classified
3. prompt_fix asset is generated
4. prompt bundle is persisted
5. bundle path is injected into version_config
6. replay can run with that prompt bundle
7. results can be compared before deciding whether to adopt the new prompt version

This is not full autonomous prompt evolution yet, but it is a valid and testable first implementation.

## 5. Recommended Next Steps

### 5.1 Make replay comparison automatic for prompt bundles
Current gap:
- prompt bundle is generated and replay-capable
- but no service automatically runs regression cases and scores the candidate bundle

Recommended implementation:
- add a service that loads recent regression cases for the affected project/section
- replay baseline vs candidate prompt bundle
- compute review metrics delta
- only promote candidate when metrics improve and false positives do not regress

### 5.2 Add explicit prompt-version registry
Current state:
- prompt versions are stored as files
- no promotion status / active version / rollback metadata

Recommended implementation:
- persist prompt versions in MySQL or a lightweight registry json
- fields:
  - version_id
  - source feedback ids
  - target templates
  - created_at
  - replay metrics
  - status: candidate / accepted / rejected / rolled_back

### 5.3 Tighten root-cause to prompt-action mapping
Current state:
- builder uses deterministic heuristics
- good enough for first loop, but still coarse

Recommended implementation:
- map specific error modes to specific templates and patch patterns:
  - missed risk -> planner/reviewer
  - false positive -> reviewer/reflector/synthesizer
  - weak evidence grounding -> retriever/reviewer
  - wrong anchor binding -> reviewer/reflector

### 5.4 Add structured prompt patch schema
Current state:
- prompt patch uses suffix instructions
- safe and easy to replay
- but still broad

Recommended implementation:
- define patch schema by slot:
  - decision_policy
  - evidence_policy
  - anchor_policy
  - output_schema_policy
- render these slots into templates deterministically

## 6. Engineering Principle For The Next Phase

Do not jump directly to autonomous prompt rewriting.
The correct order is:
1. make feedback granular and trustworthy
2. make prompt patches explicit and replayable
3. make replay comparison automatic
4. only then add automated promotion / rejection

This project is now at step 2 with part of step 3 ready.
