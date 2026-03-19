下面我按你的思路，把它整理成一套可落地的“章节预审 + 反馈优化 + 跨任务模板演化”方案。
核心目标是把现在的 4 个智能体，从“固定 prompt”升级为：

固定基线模板 + 规则库装配 + 项目级动态补丁 + 项目结束后的元反思沉淀

这样系统既能做当前项目的持续优化，也能把经验迁移到后续项目。

一、先把整体思路定型

你现在的方向是对的，而且很适合论文和系统实现。
我建议把系统拆成四层：

1. 基线模板层

每个智能体都有一份基础 prompt 模板，由系统预置，带版本号。

2. 规则装配层

把 prompt 中稳定可配置的部分抽出来，不写死在模板里，而是拆成：

通用规则

项目类型规则

审评领域规则

章节规则

反馈补丁规则

运行时动态拼接。

3. 项目级优化层

每个预审项目在运行过程中，根据反馈分析结果产生：

planner 补丁

reviewer 补丁

wording 补丁

query 补丁

reasoning 补丁

这些补丁只作用于当前项目或当前项目类型，不直接污染全局模板。

4. 元反思演化层

项目结束后，由元反思智能体对完整轨迹做总结，提炼：

可泛化经验

高收益规则

低收益/有害规则

新模板版本候选

经过人工审核后，进入全局规则库与模板版本库。

二、你这个系统最合理的运行闭环

建议做成下面这条主链：

项目创建
-> 绑定产品大类（中药/化药/生物制品）
-> 选择审评领域（药学/临床/非临床）
-> 载入对应章节结构与关注点
-> 按章节执行：
   planner -> 检索 -> reviewer
-> 用户反馈
-> feedback_analyzer
-> feedback_optimizer
-> 生成项目级 patch
-> 下一章节/下一轮审评时动态装配 patch
-> 项目结束
-> 元反思智能体总结完整轨迹
-> 形成历史经验 + 新模板候选
-> 审核通过后升级全局规则/模板版本

这个闭环里有两种优化：

1. 项目内优化

作用于当前项目后续章节和当前章节下一轮。

2. 项目后优化

作用于后续新项目。

这两层一定要分开，不然会出现“一个项目的局部经验污染全部项目”的问题。

三、建议增加一个元反思智能体

你现在有 4 个智能体，我建议再增加一个：

5. meta_reflector（元反思智能体）

作用不是参与单章节预审，而是在项目结束后处理全局经验。

输入

项目基础信息

全部章节的 planner 输出

全部检索计划与命中情况

全部 reviewer 输出

全部用户反馈

全部 feedback_analysis_result

全部 feedback_optimizer 生成的 patch

最终采用的 patch 及版本变化

章节成功率/采纳率/退回率等统计

输出

项目级经验总结

可泛化规则候选

低价值规则淘汰建议

新模板版本候选

经验适用范围

这样你整个系统就完整了：

planner / reviewer：执行预审

feedback_analyzer / feedback_optimizer：做项目内反馈闭环

meta_reflector：做跨任务演化

四、建议的规则体系

你的 prompt 不应该只是一大段文本，而应该拆成“规则插槽”。

我建议按下面 6 类规则管理。

1. 通用规则

适用于所有项目、所有智能体。

例如：

只输出 JSON

不输出 markdown

不跨章节脑补

历史经验不能替代法规依据

2. 智能体角色规则

只对某个 agent 生效。

例如：

planner 只能生成检索计划，不能下审评结论

reviewer 先抽取原文明示事实，再做判断

feedback_analyzer 必须优先使用固定 taxonomy

3. 产品类型规则

按中药 / 化药 / 生物制品区分。

例如：

化药重点关注质量标准、一致性、杂质

生物制品重点关注工艺一致性、生物活性

中药重点关注来源、炮制、指纹图谱

4. 审评领域规则

按药学 / 临床 / 非临床区分。

例如：

药学章节关注质量标准、稳定性、工艺

临床章节关注终点、样本量、获益风险

非临床章节关注毒理、药代、桥接逻辑

5. 章节级规则

按具体章节生效。

例如：

“药品名称”章节要核对中英文名、通用名、CAS、结构式

“质量标准”章节要核对检验项目、限度、方法依据

“稳定性”章节要核对条件、时长、包装、支持有效期

6. 反馈补丁规则

由 feedback_optimizer 动态生成。

例如：

如果反馈显示 query 太长且无效，则 planner 对该类章节必须优先生成短 query

如果反馈显示 reviewer 常遗漏 requested_action，则 reviewer questions 中必须显式给出申请人动作

五、规则表结构设计

建议不要只用一张表。至少做 8 张。

表 1：agent_template

存每个智能体的基线模板版本。

字段建议：

template_id

agent_name：planner / reviewer / feedback_analyzer / feedback_optimizer / meta_reflector

template_name

template_version

base_prompt_text

input_schema_json

output_schema_json

status：draft / active / deprecated

created_by

created_at

updated_at

用途：

保存完整基线模板

支持版本切换

表 2：template_rule

存规则条目，不直接写死在 prompt 里。

字段建议：

rule_id

rule_code

rule_name

rule_type：global / agent / product / domain / section / patch

target_agent：planner / reviewer / feedback_analyzer / feedback_optimizer / meta_reflector / all

rule_text

priority

is_active

version

created_at

updated_at

用途：

可装配规则

同一 agent 可挂多条规则

表 3：rule_scope_binding

定义规则适用范围。

字段建议：

binding_id

rule_id

product_type：中药 / 化药 / 生物制品 / all

review_domain：药学 / 临床 / 非临床 / all

section_name

registration_class

project_id

effective_from_round

effective_to_round

scope_type：global / project / section

用途：

同一条规则可以绑定不同范围

支持项目级 patch

表 4：template_example

存示例输入输出。

字段建议：

example_id

agent_name

template_id

example_type：input / output / good_case / bad_case

example_title

example_content

applicable_scope

priority

is_active

用途：

给 prompt 动态插入 few-shot 示例

区分好例子和坏例子

表 5：project_prompt_patch

存项目运行中由 feedback_optimizer 产生的补丁。

字段建议：

patch_id

project_id

section_id

target_agent

patch_type：query_patch / reasoning_patch / wording_patch

trigger_condition

patch_content

status：candidate / approved / rejected / applied / expired

source_feedback_id

applied_round

rollback_flag

created_at

用途：

当前项目内动态生效

支持回滚

表 6：prompt_render_snapshot

存每次实际渲染出来给模型的 prompt 快照。

字段建议：

snapshot_id

project_id

section_id

agent_name

template_id

template_version

applied_rule_ids

applied_patch_ids

rendered_prompt_text

created_at

用途：

审计与追溯

复盘为什么这个输出会这样

表 7：experience_knowledge

存元反思提炼出的长期经验。

字段建议：

experience_id

experience_type：query_rule / review_rule / wording_rule / risk_pattern

title

content

applicable_product_type

applicable_review_domain

applicable_section_name

confidence_score

source_project_count

source_patch_ids

status：candidate / approved / archived

created_at

用途：

长期经验库

可转成新规则

表 8：template_version_evolution

存模板升级记录。

字段建议：

evolution_id

agent_name

old_template_version

new_template_version

change_summary

source_experience_ids

source_project_ids

approval_status

approved_by

created_at

用途：

做全局模板升级

支持版本演化管理

六、运行时 prompt 组装逻辑

建议不要直接从 base_prompt_text 原样发给模型，而是做动态组装。

组装顺序建议如下：

planner / reviewer 的 prompt 渲染顺序

基线模板

通用规则

agent 角色规则

产品类型规则

审评领域规则

章节规则

项目级 patch

few-shot 示例

当前输入变量

你可以把这个过程称为：

Prompt Assembly Pipeline（提示词装配流水线）

这样论文里写“反馈优化系统”会很强，因为优化不是去动原模型，而是去动装配层。

七、项目内反馈优化机制

下面是你系统最关键的部分。

1. feedback_analyzer 的职责

它不负责改 prompt，只负责把反馈解释清楚。

建议固定输出三类东西：

A. 错误归因

用你已有 taxonomy 就很好：

query_miss

retrieval_scope_error

retrieval_ranking_error

historical_experience_missing

section_fact_extraction_error

focus_point_miss

evidence_interpretation_error

over_inference

under_identification

wrong_severity

wording_not_actionable

missing_regulatory_basis

unhelpful_question_to_applicant

B. 下次注意点

这些是对未来章节仍有价值的提醒。

C. 新经验候选

必须写成可复用规则，而不是复述用户原话。

2. feedback_optimizer 的职责

它不直接发布 patch，只生成 candidate。

建议你强化它的输出逻辑：

patch_type 与 target_agent 映射建议

query_patch → planner

reasoning_patch → reviewer

wording_patch → reviewer

patch_content 的格式建议

必须写成可直接拼接进规则层的一句话，例如：

“当 section_name 为质量标准且 focus_points 为空时，优先围绕药品名称、剂型和检验项目生成 3 至 5 条短 query，避免直接复制原文。”

“当 questions 涉及资料补充时，requested_action 必须写成申请人可以执行的具体动作，如补充、提供、说明、提交，不得使用模糊措辞。”

这样 patch 就可验证、可回滚、可追踪。

3. 项目内 patch 生效策略

建议不要“即时全量生效”，而是做分级。

A. 候选态

刚生成，未应用。

B. 审核通过态

允许应用到当前项目后续章节。

C. 试运行态

只在指定章节/指定轮次生效。

D. 固化态

在当前项目中全面生效。

E. 失效态

无效或被替代。

八、项目结束后的元反思机制

这是你系统区别于普通 prompt patch 的关键。

元反思输入

所有章节原文

所有 planner query_list 与 retrieval_plan

所有 reviewer 结果

所有 feedback

所有分析结果

所有 patch

最终通过/不通过统计

哪些 patch 有效，哪些无效

元反思输出建议

分四块：

1. 高频错误模式

例如：

化药药学章节中，query 经常缺失“剂型”信息，导致药典命中率低

reviewer 在“questions”中 frequently 使用模糊 requested_action

2. 高收益 patch

例如：

planner 增加“药品名称 + 产品类型 + 关注点”短 query 规则后，命中质量明显提高

3. 可泛化经验

例如：

对“质量标准”章节，若 focus_points 缺失，应优先围绕药品名称、剂型、检验项目构造药典与指导原则 query

4. 新模板候选

例如：

planner v1.3 → v1.4

reviewer v2.0 → v2.1

九、优化后的提示词模板思路

你现在的 prompt 已经不错了，但可以进一步优化成“模板 + 规则插槽”的形式。

下面我给你一个更适合系统化装配的版本思路。

1. planner 模板优化建议
目前问题

你现在 planner prompt 很完整，但有两个隐患：

规则很多，后续 patch 插入容易变乱

没有显式“动态规则插槽”

建议结构

改成：

角色定义

当前任务上下文

固定目标

当前生效规则

历史经验提醒

输出约束

schema

可插入规则区块

增加一个变量：

active_rules

模板中插一句：

“当前生效规则如下，必须优先遵守：{{ active_rules }}”

这样 patch 就不需要去重写整段 prompt。

2. reviewer 模板优化建议
当前优点

你的 reviewer 已经很接近工程可用版本了。

建议增强点

增加三个动态插槽：

active_review_rules

project_patch_rules

historical_experience_summary

并强化一个规则：

“当 retrieved_materials 支持不足时，应明确区分‘无法判断’与‘明确不支持’，不得用弱相关证据直接推出确定性缺陷。”

另外建议把 questions 再加一条硬约束：

“requested_action 应尽量对应可提交的资料、可补充的实验或可说明的事项，不得仅复述 issue。”

3. feedback_analyzer 模板优化建议
当前优点

taxonomy 很好，已经能用。

建议增强点

增加一个判断步骤：

“优先判断该问题是否可通过 prompt patch 修复；若不能，仅输出经验候选，不强制生成 patch 线索。”

这样可以减少无效 patch。

另外建议 new_experience 增加一个字段：

evidence_from_feedback

这样元反思时更容易追溯经验来源。

4. feedback_optimizer 模板优化建议
当前问题

现在它容易倾向“多生成 candidate_templates”，但 patch 的可操作性比 candidate_templates 更重要。

建议强化

增加优先级规则：

先产出最小 patch

再决定是否需要 template candidate

如果 patch 足够，则 candidate_templates 只局部增强，不要大改

再补一个规则：

“同一类 patch 若已在 current_templates 中体现，不得重复生成，只能在 applicable_conditions 中标注适用范围调整建议。”

这样可以避免 patch 膨胀。

5. meta_reflector 模板建议（新增）

建议新增下面这个 prompt。

角色定义

你是药品预审系统中的“元反思智能体”。

任务

综合分析项目全流程轨迹；

识别高频错误模式和高收益补丁；

提炼可跨任务复用的经验规则；

生成新的模板版本候选；

指出哪些 patch 不应升级为全局规则。

输出建议
{
  "project_id": "string",
  "high_frequency_error_patterns": ["string"],
  "high_value_patches": [
    {
      "patch_id": "string",
      "reason": "string",
      "recommended_upgrade": "global_rule|product_rule|domain_rule|section_rule|keep_project_only"
    }
  ],
  "new_global_experience": [
    {
      "experience_type": "query_rule|review_rule|wording_rule|risk_pattern",
      "content": "string",
      "applicable_scope": "string"
    }
  ],
  "template_upgrade_candidates": {
    "planner_template_delta": ["string"],
    "reviewer_template_delta": ["string"]
  },
  "rules_to_archive": ["string"],
  "summary": "string"
}
十、建议的“经验生效”分层

这是系统治理上很重要的一点。

经验不要一次性全局生效，建议分 4 层
层 1：项目临时 patch

只作用于当前项目。

层 2：产品类型经验

例如只对化药生效。

层 3：审评领域经验

例如只对药学生效。

层 4：全局经验

适用于所有项目。

这样做能防止“化药药学经验污染中药临床”。

十一、最推荐的规则表组合

如果你想最小可用，我建议至少先做 6 张，不用一开始 8 张全上：

agent_template

template_rule

rule_scope_binding

project_prompt_patch

prompt_render_snapshot

experience_knowledge

这 6 张已经能支撑：

基线模板

规则装配

项目 patch

审计追踪

长期经验沉淀