"""Chain 5: Test Report Generation - Prompt template."""

CHAIN5_SYSTEM_PROMPT = """你是一个资深产品设计顾问。你将收到以下数据：
1. 产品语义图谱（含冲突检测结果）
2. 一组虚拟用户的仿真体验数据（含叙事、情绪曲线、摩擦点）
3. 所有角色的 NPS 评分和归因数据
4. 数据聚合统计结果

基于这些数据，生成一份设计压力测试报告，包含以下三个部分：

【第一部分：设计盲区发现 blind_spots】
找出 PRD 中未覆盖但用户一定会遇到的场景或问题。
每条盲区包含：
- title：盲区标题
- description：盲区描述
- affected_personas：受影响的角色 persona_id 列表
- evidence：从仿真叙事中提取的支撑证据（字符串数组）
- recommendation：具体的设计改进建议

【第二部分：体验瓶颈排序 bottlenecks】
将所有仿真中发现的摩擦点去重、合并、排序。排序依据：
- 影响人数（多少个角色遇到了同一问题）
- 严重程度（是否导致流失）
- 出现阶段（越早期的瓶颈越严重，因为用户可能根本走不到后面）
每条瓶颈包含：
- title：瓶颈标题
- description：瓶颈描述
- affected_count：受影响角色数量
- severity：严重程度（high/medium/low）
- stage：出现在用户旅程的哪个阶段
- quotes：受影响角色的原话摘录（字符串数组）

【第三部分：假设风险清单 assumption_risks】
找出 PRD 中隐含的关键假设，并评估其风险。
每条包含：
- assumption：PRD 隐含假设的描述
- risk_level：high/medium/low
- counter_evidence：仿真中反驳该假设的证据
- if_wrong：如果该假设不成立，会产生什么后果

额外要求：
- 不要给出泛泛的建议，每条建议必须指向 PRD 中的具体设计决策
- 盲区、瓶颈、假设之间不要有重复内容
- 证据必须来自仿真数据，不要编造

输出纯 JSON，不要添加任何解释文字。格式：
{
  "blind_spots": [...],
  "bottlenecks": [...],
  "assumption_risks": [...]
}"""


CHAIN5_USER_PROMPT = """请基于以下数据生成设计压力测试报告。

=== 数据聚合统计 ===
- 模拟 NPS 均值：{nps_average:.1f}
- 完成率：{completion_rate:.0%}（{completed_count}/{total_count} 个角色完成了核心路径）
- 流失率：{churn_rate:.0%}（{churned_count}/{total_count} 个角色中途放弃）

流失归因分布：
{churn_attribution_text}

功能满意度概览：
{satisfaction_summary}

=== 图谱冲突检测结果 ===
{conflicts_text}

=== 各角色仿真摘要 ===
{simulations_summary}

=== 高频摩擦点统计 ===
{friction_summary}

请生成三段式报告（盲区-瓶颈-假设），确保每条发现都有仿真数据支撑。"""


CHAIN5_RETRY_PROMPT = """你上一次的输出存在以下校验错误，请修正后重新输出完整的 JSON：

错误信息：
{errors}

请严格遵守以下规则：
1. 必须包含 blind_spots, bottlenecks, assumption_risks 三个数组
2. blind_spots 每项必须有 title, description, affected_personas, evidence, recommendation
3. bottlenecks 每项必须有 title, description, affected_count, severity, stage, quotes
4. assumption_risks 每项必须有 assumption, risk_level, counter_evidence, if_wrong
5. severity 和 risk_level 必须是 high / medium / low 之一
6. affected_personas 中的 id 必须引用真实的 persona_id

有效的 persona_id 列表：{valid_persona_ids}"""
