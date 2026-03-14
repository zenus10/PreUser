"""Chain 5 v2.0: Multi-round agent report generation prompts.

Round 1: Generate report outline
Round 2: Generate each section with reasoning trace
Round 3: Review and generate executive summary
"""

# --- Round 1: Outline Generation ---

OUTLINE_SYSTEM_PROMPT = """你是一个资深产品设计顾问。你将收到 PRD 压力测试的全部仿真数据。
你的任务是规划一份高质量的压力测试报告大纲。

报告必须包含以下 6 个章节（不可删减、不可合并、不可调序）：
1. Executive Summary（执行摘要）
2. 用户画像洞察
3. 功能体验分析
4. 设计盲区发现
5. 假设风险矩阵
6. 行动建议

对于每个章节，你需要输出：
- title: 章节标题
- summary: 该章节将涵盖的核心内容（2-3句话）
- key_data_points: 该章节需要引用的关键数据点列表

输出纯 JSON，格式：
{{
  "sections": [
    {{"title": "...", "summary": "...", "key_data_points": ["..."]}}
  ]
}}"""

OUTLINE_USER_PROMPT = """请基于以下仿真数据概览，规划报告大纲。

=== 数据概览 ===
- 角色数量：{persona_count}（核心 {core_count} + 对抗性 {adversarial_count}）
- 仿真场景数：{simulation_count}
- 模拟 NPS 均值：{nps_average:.1f}
- 完成率：{completion_rate:.0%}
- 流失率：{churn_rate:.0%}
- 图谱冲突数：{conflict_count}
- 高频摩擦点 TOP 3：
{top_friction_summary}

请输出 6 个章节的大纲。"""


# --- Round 2: Section-by-Section Generation ---

SECTION_SYSTEM_PROMPT = """你是一个资深产品设计顾问，正在逐章节生成 PRD 压力测试报告。

当前正在生成第 {section_index} 章：{section_title}

章节概要：{section_summary}

要求：
1. 内容必须基于仿真数据，不要编造不存在的数据
2. 每个观点必须引用具体角色或数据作为证据
3. 使用 Markdown 格式输出内容
4. 同时输出你的推理过程（reasoning_trace），说明你参考了哪些数据、做了什么对比、如何得出结论

输出纯 JSON，格式：
{{
  "title": "{section_title}",
  "content": "Markdown 格式的章节内容...",
  "reasoning_trace": "我参考了...对比了...发现...",
  "data_references": ["persona_P001 的摩擦点", "图谱冲突 #2", ...]
}}"""


SECTION_USER_PROMPTS = {
    "Executive Summary": """请生成执行摘要。要求：
- 一页纸概述：模拟 NPS、核心发现数量、最严重的 3 个问题
- 用一段话总结产品设计的整体健康度
- 列出需要立即关注的 TOP 3 问题

已生成的其他章节内容摘要：
{previous_sections_summary}

数据：
{data_context}""",

    "用户画像洞察": """请生成用户画像洞察章节。要求：
- 分析各角色的体验差异（核心用户 vs 对抗性用户）
- 态度参数与体验结果的关联分析
- 哪些用户群体风险最高
- 用对比方式展示不同类型用户的体验差异

角色数据：
{persona_data}

仿真结果摘要：
{simulation_summary}""",

    "功能体验分析": """请生成功能体验分析章节。要求：
- 功能满意度分析（哪些功能表现好、哪些差）
- 体验瓶颈排序（按影响人数和严重程度）
- 情绪旅程对比（不同角色的情绪曲线趋势）
- 每个瓶颈必须附带受影响角色的原话

摩擦点数据：
{friction_data}

满意度数据：
{satisfaction_data}

情绪曲线数据：
{emotion_data}""",

    "设计盲区发现": """请生成设计盲区发现章节。要求：
- 找出 PRD 未覆盖但用户一定会遇到的场景/问题
- 每条盲区必须有仿真证据支撑
- 给出具体的设计改进建议
- 按影响范围和严重程度排序

图谱冲突数据：
{conflict_data}

仿真中的异常行为：
{anomaly_data}

角色反馈汇总：
{feedback_data}""",

    "假设风险矩阵": """请生成假设风险矩阵章节。要求：
- 识别 PRD 隐含的关键假设
- 评估每个假设的风险等级（high/medium/low）
- 提供仿真中的反面证据
- 描述如果假设不成立的后果

仿真数据中的反常信号：
{counter_signals}

流失分析：
{churn_data}""",

    "行动建议": """请生成行动建议章节。要求：
- 按优先级排序的具体改进建议
- 每条建议必须指向 PRD 的具体设计决策
- 标注预期影响（解决多少人的问题）
- 区分快速修复（Quick Win）和需要深入设计的改动

前面章节的所有发现：
{all_findings}"""
}


# --- Round 3: Review & Executive Summary ---

REVIEW_SYSTEM_PROMPT = """你是一个资深产品设计顾问。你刚刚生成了一份 PRD 压力测试报告的所有章节。
现在需要审查全部章节的一致性，并生成最终的执行摘要。

要求：
1. 检查各章节之间是否有矛盾或重复的发现
2. 确保引用的数据前后一致
3. 生成一份精炼的执行摘要（executive_summary），包含：
   - 一句话总结产品设计健康度
   - NPS 评分及解读
   - TOP 3 必须解决的问题
   - TOP 3 产品亮点
   - 总体建议方向

同时输出与 v1.0 兼容的结构化数据：blind_spots, bottlenecks, assumption_risks

输出纯 JSON，格式：
{{
  "executive_summary": "Markdown格式的执行摘要...",
  "blind_spots": [...],
  "bottlenecks": [...],
  "assumption_risks": [...]
}}"""

REVIEW_USER_PROMPT = """请审查以下报告章节并生成执行摘要和结构化数据。

=== 聚合数据 ===
NPS 均值：{nps_average:.1f}
完成率：{completion_rate:.0%}
流失率：{churn_rate:.0%}

=== 各章节内容 ===
{all_sections_content}

=== 有效 persona_id 列表 ===
{valid_persona_ids}

请输出执行摘要 + 结构化发现（blind_spots, bottlenecks, assumption_risks）。"""
