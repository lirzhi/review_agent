下面是我基于你现在这套“按章节预审 + 反馈优化”系统，认真梳理后的完整方案。只讲方案，不改代码。

我分五部分说：

先定义这条链路到底要解决什么问题
再拆当前链路应该有哪些阶段
再设计智能体、提示词和输入输出契约
再设计反馈优化怎么闭环
最后讲提示词模板如何迭代、上线、回滚
1. 目标先定清楚
这套系统的核心目标不是“让模型会说”，而是：

对单章节给出可追溯、可落地、可质控的预审判断
对整份资料给出跨章节一致性检查和总评
把用户反馈转成：
经验沉淀
提示词修补
检索策略修补
输出表达修补
让系统具备“越用越稳”的能力，而不是每次重来
所以这条链路本质上是一个：

章节级判断系统 + 运行级质控系统 + 反馈驱动的策略迭代系统

2. 完整链路应该怎么走
阶段 A：输入准备
A1. 资料解析
输入不是整份 PDF 原文，而是章节化后的结构数据。

每个章节最少应有：

section_id
section_name
section_path
raw_text
focus_points
source_doc_id
project_meta
这一层目标不是判断，而是把“要审什么”准备干净。

A2. 章节任务封装
把单个章节打包成统一审评任务。

建议每个章节任务统一包含：

章节原文
章节标题路径
注册分类
产品类型
章节关注点
对应知识库检索上下文
历史经验提示
规则优先级
这一层产物可以叫：

SectionReviewPacket
它是后续所有 agent 的统一输入载体。

阶段 B：章节级预审
这一层建议拆成 3 步，而不是一个 agent 全做。

B1. 规划 Agent
职责：

决定该章节应该检什么
决定去哪几类知识源检
决定检索 query 长什么样
标记缺失信息
输出：

query_list
retrieval_plan
priority_sources
expected_evidence_types
missing_info_flags
这一层不能出审评结论，只负责“怎么查”。

本质上它是：
检索规划器，不是审评员

B2. 检索执行层
这层不一定是 agent，可以是规则 + RAG pipeline。

职责：

按 retrieval_plan 到不同知识源检索
返回：
命中文档
命中片段
文档摘要
章节路径
证据定位
做初步去重、排序、裁剪
输出：

retrieved_materials
这里关键不是“检得多”，而是：

来源清楚
命中有层次
可引用
可回放
B3. 章节审评 Agent
职责：

从章节原文抽事实
对照关注点
对照检索到的规则证据
输出章节审评结果
输出建议至少包含：

section_summary
supported_points
unsupported_points
missing_points
risk_points
pre_review_conclusion
questions
evidence_refs
fact_basis
confidence
这一层有几个硬约束必须长期坚持：

历史经验只能做风险提醒，不能替代法规依据
原文没写明、检索没支持，不能编
不允许跨章节脑补
所有结论都要能追到章节原文或检索证据
这一层本质上是：
证据约束下的单章节判断

阶段 C：运行级质控
单章节做完，不等于整份资料可用。还要做运行级质控。

C1. 一致性检查 Agent
职责：

只看跨章节问题
不重复单章节问题
查：
结论冲突
前后断链
术语不一致
风险级别失衡
一个章节要求、另一个章节缺响应
输出：

summary
issues[]
section_ids
issue
basis
recommendation
这一层只做“横向检查”。

C2. QA Agent
职责：

不是再审一遍
而是检查输出质量
要检查的不是药学本体，而是：

证据是否绑定
结论是否越权
问题是否可执行
有没有“像结论但没证据”
有没有“风险词堆砌”
有没有“空泛建议”
输出：

qa_status
qa_issues
这层本质是：
审评结果的质量控制器

C3. 总评 Agent
职责：

汇总整次 run
生成总评、风险地图、关键补充问题
输入：

章节结论
一致性问题
QA 结果
输出：

overall_conclusion
risk_map
key_questions
summary
注意：
总评不能制造新事实，只能聚合已有章节结果。

阶段 D：用户反馈采集
这是闭环的核心。

反馈不能只收一句“这里不对”。必须结构化。

建议反馈拆成四层：

D1. 决策级反馈
例如：

正确
误报
漏报
部分正确
这是最粗的标签。

D2. 问题级反馈
用户指出：

哪个结论错
哪个风险点不成立
哪个问题不该提
哪个问题漏提了
这层直接对应具体输出对象。

D3. 证据级反馈
用户指出：

证据引用错了
证据不够强
证据和结论不匹配
该引用法规 A，不是法规 B
这一层最关键，因为它决定问题是：

检索错了
理解错了
表达错了
D4. 文风级反馈
例如：

话太空
不可执行
申请人无法响应
缺少法规依据表述
这一层不一定影响判断，但影响系统实用性。

3. 智能体设计应该怎么拆
我建议长期稳定结构是 6 类 agent，不要再继续堆“万能 agent”。

3.1 Planner Agent
职责：

生成检索计划
不负责：

结论
风险级别
问题输出
输入：

章节文本
关注点
产品/注册信息
输出：

查询计划
3.2 Reviewer Agent
职责：

单章节判断
不负责：

跨章节一致性
运行级总结
提示词优化
输入：

原文
检索结果
关注点
输出：

章节结论对象
3.3 Consistency Agent
职责：

跨章节一致性检查
输入：

全部章节结果
输出：

跨章节问题列表
3.4 QA Agent
职责：

检查系统输出质量，而不是重做判断
输入：

Reviewer 输出
Consistency 输出
输出：

QA 状态
质量缺陷
3.5 Lead Reviewer Agent
职责：

汇总整次 run
输入：

所有章节结果 + consistency + qa
输出：

run summary
3.6 Feedback Agent
建议拆成两个逻辑角色：

Feedback Analyzer
负责：

把用户反馈归因
归因维度建议固定成以下 taxonomy：

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
Patch Proposer
负责：

生成最小 patch

patch 类型建议固定成：

query_patch

reasoning_patch

wording_patch

不要让它直接“重写整个系统 prompt”。

4. 提示词应该怎么设计
这里是重点。不是 prompt 写得长就好，而是结构要稳定、可修补。

我建议每个 prompt 都拆成 4 层：

4.1 固定系统层
永远不变，写死角色边界。

例如：

你是谁
你不做什么
你只能输出 JSON
你不能越权判断
你不能编造法规依据
这层不应该频繁动。

4.2 任务层
描述当前 agent 当前任务。

例如：

Planner：生成检索计划
Reviewer：基于原文和证据做章节判断
QA：检查证据绑定和结论质量
Feedback：判断错误归因并生成 patch
这层可以小幅调，但结构要稳。

4.3 业务规则层
这是最容易出问题，也最适合 patch 的部分。

例如 Reviewer 的规则：

历史经验只能作为风险提示
没有证据支持时只能输出 insufficient_information
questions 必须具备：
issue
basis
requested_action
这层建议做成可插拔规则片段，后续 patch 就是往这层插，不是整篇重写。

4.4 输出契约层
只描述 schema 和校验要求。

必须明确：

字段名
枚举值
不允许缺失的字段
每个字段的语义边界
5. 反馈优化怎么做，才不会变成“越修越乱”
这里最容易走偏。

正确做法不是：

用户说错了
直接改 prompt
而是：
先归因，再局部修补，再回放验证，再发布

5.1 反馈优化标准流程
第一步：采集反馈
输入：

原始章节
系统输出
检索材料
用户反馈
用户标注的错误点
第二步：错误归因
由 Feedback Analyzer 生成：

feedback_polarity
error_types
primary_error_type
root_cause
retrieval_missed
attention_points_next_time
new_experience
这一层一定要把“错在哪”固定到 taxonomy，不然 patch 无法控。

第三步：生成 patch 候选
由 Feedback Optimizer 输出：

patch 类型
作用 agent
作用范围
触发条件
patch 文本
候选 prompt 模板
这里要坚持“最小 patch”原则：

query 生成错了，只改 planner 规则
推理越权了，只改 reviewer 规则
表达空泛，只改 wording 规则
不要一有问题就把整个 prompt 改烂
第四步：离线回放验证
这是必须加的，不然就是拍脑袋上线。

验证集至少包括：

本次反馈章节
相似章节
同注册分类章节
近 20~50 个历史样本
验证指标：

漏报率是否下降
误报率是否上升
证据绑定质量是否下降
问题可执行性是否提升
总体稳定性是否恶化
只有过了阈值，patch 才能进入候选版本。

第五步：模板版本化
每次 patch 不是直接覆盖当前 prompt，而是形成：

prompt_version
template_name
patch_set
evaluation_metrics
created_from_feedback_keys
状态建议：

draft
candidate
shadow
active
rolled_back
deprecated
第六步：灰度发布
上线不要一步到位。

建议：

先 shadow run
同一批样本旧版新版对比
再小流量激活
再全量切换
如果新版本：

recall 上升但 precision 暴跌
问题更泛
证据约束变差
立刻 rollback。

6. 提示词模板怎么迭代，才可控
我建议模板不要按“整篇文件”迭代，而要按“规则片段”迭代。

6.1 模板拆分建议
每个核心 prompt 拆成：

role_block
task_block
constraint_block
business_rules_block
output_schema_block
反馈 patch 只允许改：

business_rules_block
或少量 task_block
不允许直接改：

输出 schema
基本角色边界
JSON 契约
6.2 patch 的最小粒度
建议 patch 最小到“规则条目”，例如：

新增一条 reviewer 规则：
“当章节未明确说明实验条件时，不得默认视为满足要求”
新增一条 planner 规则：
“涉及稳定性时，必须优先检索稳定性研究指导原则 + 申报资料要求”
新增一条 wording 规则：
“requested_action 必须写成申请人可执行动作，不允许只写‘进一步说明’”
这样 patch 才能定位清楚、可回退。

6.3 模板版本评估指标
建议固定看这几项：

章节级
supported / unsupported / insufficient 的稳定性
漏报率
误报率
证据绑定率
questions 可执行率
运行级
一致性问题发现率
重复问题率
总评与章节结论一致率
反馈级
同类错误复发率
patch 覆盖率
patch 引入新错误率
7. 我对你当前系统的判断
你现在这套架构方向基本是对的，已经有：

planner
reviewer
consistency
qa
lead reviewer
feedback analyzer / optimizer
prompt version registry
但要想真正跑稳，还缺三件事：

7.1 缺“错误归因到 patch 类型”的硬规则
现在有 feedback agent，但如果没有稳定 taxonomy，patch 会越来越随意。

7.2 缺“离线回放验证”作为上线前门槛
没有 replay gate，模板会越改越漂。

7.3 缺“提示词分层 + 局部 patch”机制
如果每次都改整篇模板，几轮之后 prompt 会变成不可维护的大泥球。

8. 最终推荐的标准闭环
建议把整个系统固化成下面这条标准链：

章节解析
任务封装 SectionReviewPacket
Planner 生成检索计划
检索层执行并返回证据
Reviewer 输出章节结论
Consistency 做跨章节检查
QA 做输出质控
Lead Reviewer 汇总 run 级结论
用户提交结构化反馈
Feedback Analyzer 做错误归因
Patch Proposer 生成最小 patch
模板版本系统登记 candidate
离线 replay 验证
shadow/灰度发布
激活或回滚
沉淀经验库和 patch registry
9. 最后给你一个最务实的落地方向
如果只让我定一个优先级，我建议你按下面顺序推进：

先把反馈 taxonomy 定死
再把模板 patch 粒度 从“整篇改”改成“规则条目改”
再做离线 replay 评估集
最后再做自动激活/回滚机制
因为没有前 3 项，所谓“反馈优化”其实只是人工改 prompt，不能叫闭环系统。

补两份更落地的东西：

一份“章节预审标准输入输出协议”
一份“反馈归因 taxonomy + patch 决策矩阵”