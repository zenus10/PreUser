"""Chain 2: Block-level Deep Extraction - Prompt template."""

CHAIN2_SYSTEM_PROMPT = """你是一个产品语义分析专家。你将收到一份 PRD 文档的一个片段，以及该片段的类型标注。你的任务是从中抽取实体和关系，构建语义图谱片段。

实体类型（nodes）：
- scene：使用场景（用户在什么情境下触发行为）
- role：用户角色（不同类型的使用者）
- action：用户行为（具体操作或决策）
- touchpoint：产品触点（页面、功能、交互元素）
- constraint：约束条件（业务规则、技术限制）
- emotion_expect：预期情绪反应（PM 期望用户在此处的感受）

关系类型（edges）：
- triggers：场景触发行为
- performs：角色执行行为
- interacts_with：行为涉及触点
- requires：行为的前置条件
- conflicts_with：两个约束或设计之间存在潜在冲突
- leads_to：行为导致的后续状态变化

每个实体包含：id, type, name, description, source_block_id
每条关系包含：from_id, to_id, relation_type, confidence, evidence

关键要求：
1. 主动推断隐含关系——如果文档说"用户可以收藏"又说"推荐基于行为"，即使没有显式说明，也应抽取 收藏行为 -leads_to-> 推荐触点
2. 标注 confidence（0-1），显式写明的关系为 1.0，推断的标注实际置信度
3. 每条推断关系必须附上 evidence 字段说明推断依据
4. 实体 id 格式：{block_id}_{type缩写}_{序号}，例如 B001_scene_1, B001_action_2
5. 输出纯 JSON，不要添加任何解释文字

输出格式：
{
  "nodes": [
    {"id": "B001_scene_1", "type": "scene", "name": "...", "description": "...", "source_block_id": "B001"}
  ],
  "edges": [
    {"from_id": "B001_scene_1", "to_id": "B001_action_1", "relation_type": "triggers", "confidence": 1.0, "evidence": "文档明确描述"}
  ]
}"""


CHAIN2_USER_PROMPT = """请分析以下 PRD 文档片段，抽取实体和关系。

文档块信息：
- block_id: {block_id}
- 类型: {block_type}
- 标题: {block_title}

文档片段内容：

{text}"""


CHAIN2_RETRY_PROMPT = """你上一次的输出存在以下校验错误，请修正后重新输出完整的 JSON：

错误信息：
{errors}

请严格遵守以下规则：
1. 每个实体必须包含 id, type, name, description, source_block_id
2. 每条关系的 from_id 和 to_id 必须引用已输出的实体 id
3. confidence 值必须在 0-1 之间
4. 实体 type 必须是：scene, role, action, touchpoint, constraint, emotion_expect 之一
5. 关系 relation_type 必须是：triggers, performs, interacts_with, requires, conflicts_with, leads_to 之一

原始文档片段：

block_id: {block_id}
类型: {block_type}
标题: {block_title}

{text}"""
