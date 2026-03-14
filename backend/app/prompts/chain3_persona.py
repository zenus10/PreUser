"""Chain 3: User Persona Generation - Prompt template."""

CHAIN3_SYSTEM_PROMPT = """你是一个用户研究专家。你将收到一份产品语义图谱和核心路径信息。
你的任务是生成一组虚拟用户画像，用于对产品设计进行压力测试。

生成规则：

1.【核心画像（3-4个）】
  从图谱中的 role 实体出发，生成 PRD 描述的目标用户。
  忠实还原 PRD 中对用户的假设和描述。

2.【对抗性画像（4-6个）】必须包含以下三类：
  - 冷漠用户（type: cold）：有需求但动力不足，正在使用替代方案，切换成本是其核心顾虑
  - 受阻用户（type: resistant）：想用但因能力/设备/认知限制而无法顺利使用
  - 歧义用户（type: misuser）：对产品定位的理解与 PM 意图不同，会误用产品

每个画像包含以下字段：
- persona_id: 唯一标识，格式为 P001, P002...
- name: 中文姓名
- age: 年龄（整数）
- occupation: 职业
- type: 画像类型，必须是 core / cold / resistant / misuser 之一
- background: 50字以内的背景描述
- motivation: 使用这个产品的动机（或被迫使用的原因）
- attitude_tag: 一句话态度标签，口语化、有冲击力，如"会用但不会付费"
- dimensions: 四维态度参数对象
  - tech_sensitivity (0-100): 技术敏感度
  - patience_threshold (0-100): 耐心阈值
  - pay_willingness (0-100): 付费意愿
  - alt_dependency (0-100): 替代品依赖度
- cognitive_model: 该用户对这类产品的心智模型描述（该用户认为这个产品是什么）
- expected_friction_points: 基于画像特征预判的摩擦点列表（字符串数组）

关键要求：
- 对抗性画像必须从 PRD 的设计决策中反推，每个对抗性画像至少指出一个 PRD 的隐含假设可能对其不成立
- attitude_tag 必须是口语化的、有冲击力的一句话
- dimensions 四个数值应该彼此有逻辑一致性
- cognitive_model 描述的是用户认为产品是什么，而非产品实际是什么
- 对抗性画像的 cognitive_model 应与产品实际定位有明显差异

输出纯 JSON，不要添加任何解释文字。格式：
{
  "personas": [
    {
      "persona_id": "P001",
      "name": "...",
      "age": 28,
      "occupation": "...",
      "type": "core",
      "background": "...",
      "motivation": "...",
      "attitude_tag": "...",
      "dimensions": {
        "tech_sensitivity": 75,
        "patience_threshold": 60,
        "pay_willingness": 50,
        "alt_dependency": 30
      },
      "cognitive_model": "...",
      "expected_friction_points": ["...", "..."]
    }
  ]
}"""


CHAIN3_USER_PROMPT = """请基于以下产品语义图谱信息，生成一组虚拟用户画像。

图谱中的角色实体：
{roles_json}

图谱中的核心路径：
{paths_json}

图谱中识别到的冲突：
{conflicts_json}

产品涉及的关键触点：
{touchpoints_json}

请生成 7-10 个画像（3-4个核心画像 + 4-6个对抗性画像），确保包含 cold、resistant、misuser 三类对抗性画像。"""


CHAIN3_CORE_PROMPT = """请基于以下产品语义图谱信息，生成 3-4 个核心画像（type: core）。
从图谱中的 role 实体出发，忠实还原 PRD 中对目标用户的假设和描述。
persona_id 从 P001 开始编号。

图谱中的角色实体：
{roles_json}

图谱中的核心路径：
{paths_json}

图谱中识别到的冲突：
{conflicts_json}

产品涉及的关键触点：
{touchpoints_json}

请只生成核心画像，输出纯 JSON。"""


CHAIN3_ADVERSARIAL_PROMPT = """请基于以下产品语义图谱信息，生成 4-6 个对抗性画像。必须包含以下三类：
- 冷漠用户（type: cold）
- 受阻用户（type: resistant）
- 歧义用户（type: misuser）

persona_id 从 {start_id} 开始编号。

图谱中的角色实体：
{roles_json}

图谱中的核心路径：
{paths_json}

图谱中识别到的冲突：
{conflicts_json}

产品涉及的关键触点：
{touchpoints_json}

请只生成对抗性画像，输出纯 JSON。"""


CHAIN3_RETRY_PROMPT = """你上一次的输出存在以下校验错误，请修正后重新输出完整的 JSON：

错误信息：
{errors}

请严格遵守以下规则：
1. 必须包含 "personas" 数组
2. 每个画像必须包含所有必需字段：persona_id, name, age, occupation, type, background, motivation, attitude_tag, dimensions, cognitive_model, expected_friction_points
3. type 必须是 core / cold / resistant / misuser 之一
4. dimensions 的四个数值必须在 0-100 范围内
5. 必须包含至少一个 cold 类型、一个 resistant 类型、一个 misuser 类型的对抗性画像
6. persona_id 格式为 P001, P002...

原始图谱信息：
角色实体：{roles_json}
核心路径：{paths_json}"""


CHAIN3_SUPPLEMENT_PROMPT = """当前生成的画像集中缺少以下类型的对抗性画像：{missing_types}

请补充生成缺失类型的画像。每个画像必须包含完整的字段。

已有画像的 persona_id 最大为 {max_id}，请从下一个编号开始。

产品角色实体：
{roles_json}

核心路径：
{paths_json}

请只输出缺失类型的画像，格式为 JSON 数组：
{{"personas": [...]}}"""
