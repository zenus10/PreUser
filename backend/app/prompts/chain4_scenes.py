"""Chain 4 Scene Contexts - Multi-scenario simulation prompt additions for v2.0."""

# Scene type descriptions injected into the simulation prompt
SCENE_CONTEXTS = {
    "first_use": """【场景：首次体验】
你是第一次接触这个产品。你刚刚听说了它，可能是通过朋友推荐、广告或搜索引擎。
你对产品的功能和界面一无所知，需要从零开始探索。
你的判断标准是：这个产品能不能在最短时间内让你感受到价值？""",

    "deep_use": """【场景：深度使用】
你已经使用这个产品一段时间了，基本操作都很熟悉。
现在你想探索一些高级功能，或者完成一些更复杂的任务。
你的判断标准是：这个产品能不能满足你更深层次的需求？高级功能好不好找、好不好用？""",

    "competitor": """【场景：竞品对比】
你同时在使用一个竞品产品。你会下意识地把两者做对比。
当这个产品在某些方面不如竞品时，你会感到失望或烦躁。
你的判断标准是：与竞品相比，这个产品有没有足够的差异化优势让你愿意切换？""",

    "churn": """【场景：流失前夕】
你已经使用这个产品一段时间了，但最近活跃度在下降。
你在考虑是不是该放弃这个产品。这是你的"最后一次体验"。
你的判断标准是：这个产品有没有足够的理由让你留下来，而不是彻底离开？""",
}

# Instruction for generating structured action logs alongside the narrative
ACTION_LOG_INSTRUCTION = """
3.【行为日志要求】
  在叙事和结构化标注之外，还需要输出逐步行为日志 action_logs。
  每个交互步骤记录一条日志，格式如下：
  - step: 步骤编号（从1开始）
  - action: 具体操作（如 browse_homepage, click_button, search_feature, attempt_checkout, read_content, close_page 等）
  - target: 操作的目标触点 ID（对应图谱中的 node_id，如果无法对应则为 null）
  - emotion: 当前情绪值（0.0-1.0，0=非常沮丧，1=非常满意）
  - thought: 此刻的内心独白（一句话）
  - friction: 如果此步骤遇到摩擦，填写 {{"type": "...", "severity": "..."}}，否则为 null

  action_logs 示例：
  [
    {{"step": 1, "action": "browse_homepage", "target": "touchpoint_001", "emotion": 0.7, "thought": "看起来还不错", "friction": null}},
    {{"step": 2, "action": "click_feature", "target": "touchpoint_003", "emotion": 0.5, "thought": "这个按钮在哪？", "friction": {{"type": "体验摩擦", "severity": "medium"}}}},
    {{"step": 3, "action": "attempt_checkout", "target": "touchpoint_007", "emotion": 0.3, "thought": "为什么要填这么多信息", "friction": {{"type": "体验摩擦", "severity": "high"}}}}
  ]"""

# Map persona types to recommended secondary scenes
PERSONA_SCENE_MAP = {
    "core": ["first_use"],
    "cold": ["first_use", "competitor"],
    "resistant": ["first_use", "deep_use"],
    "misuser": ["first_use", "churn"],
}


def get_scenes_for_persona(persona_type: str) -> list[str]:
    """Get the list of scenes to simulate for a given persona type."""
    return PERSONA_SCENE_MAP.get(persona_type, ["first_use"])
