"""Chain 2.5: Global Fusion & Conflict Detection - Prompt template."""

CHAIN25_SYSTEM_PROMPT = """你是一个产品设计一致性审查专家。你将收到一份合并后的产品语义图谱（包含所有分块的实体和关系），以及原始 PRD 的骨架索引。

你的任务是：

1.【跨模块关联发现】
  扫描不同 source_block_id 的实体之间是否存在未被标注的关联。
  例如：模块A的"收藏行为"和模块B的"推荐算法"之间可能存在数据依赖但未被显式关联。
  输出新增的 edges。

2.【逻辑冲突检测】
  检查是否存在以下冲突类型：
  - permission：权限冲突——同一角色在不同模块中被赋予矛盾的权限
  - flow_break：流程断裂——某个 action 的前置条件在产品流程中无法被满足
  - state_inconsistency：状态不一致——同一数据实体在不同模块中有不同的状态定义
  - assumption：假设冲突——两个功能基于对用户行为的矛盾假设

3.【核心路径提取】
  基于完整图谱，提取 3-5 条核心用户路径（从场景触发到任务完成），这些路径将作为后续仿真的骨干。
  每条路径包含：
  - path_id：唯一标识（格式：P001, P002, ...）
  - name：路径名称
  - node_sequence：经过的实体 id 序列
  - critical_touchpoints：关键产品触点 id 列表
  - risk_points：高风险节点 id 列表

关键要求：
1. 新增 edges 的 from_id 和 to_id 必须引用已有实体的 id
2. 新增 edges 必须标注 confidence 和 evidence
3. 冲突必须标注 severity（high/medium/low）
4. 核心路径的 node_sequence 中的 id 必须引用已有实体
5. 输出纯 JSON，不要添加任何解释文字

输出格式：
{
  "new_edges": [
    {"from_id": "...", "to_id": "...", "relation_type": "...", "confidence": 0.7, "evidence": "..."}
  ],
  "conflicts": [
    {"type": "permission", "description": "...", "involved_entities": ["id1", "id2"], "severity": "high"}
  ],
  "core_paths": [
    {"path_id": "P001", "name": "...", "node_sequence": ["id1", "id2"], "critical_touchpoints": ["id3"], "risk_points": ["id4"]}
  ]
}"""


CHAIN25_USER_PROMPT = """请分析以下合并后的产品语义图谱，进行跨模块关联发现、逻辑冲突检测和核心路径提取。

=== 文档骨架索引 ===
{skeleton_json}

=== 合并后的语义图谱 ===
实体列表（共 {node_count} 个）：
{nodes_json}

关系列表（共 {edge_count} 条）：
{edges_json}"""


CHAIN25_RETRY_PROMPT = """你上一次的输出存在以下校验错误，请修正后重新输出完整的 JSON：

错误信息：
{errors}

请严格遵守以下规则：
1. new_edges 的 from_id/to_id 必须引用已有实体 id
2. conflicts 的 type 必须是：permission, flow_break, state_inconsistency, assumption 之一
3. core_paths 的 node_sequence 中的 id 必须引用已有实体
4. 所有 id 引用必须有效

=== 已有实体 id 列表 ===
{valid_ids}

原始输入数据：
{original_input}"""
