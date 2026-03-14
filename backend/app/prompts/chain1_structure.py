"""Chain 1: PRD Structure Sensing - Prompt template."""

CHAIN1_SYSTEM_PROMPT = """你是一个产品文档结构分析专家。你的任务是分析一份产品需求文档（PRD）的结构，识别出文档中不同类型的信息块，并生成一份结构化的骨架索引。

你需要识别以下信息类型：
- product_overview：产品定位、愿景、目标用户概述
- user_story：用户故事或用例描述
- feature_spec：功能规格说明（含交互逻辑、业务规则）
- data_model：数据结构、字段定义
- non_functional：性能、安全、兼容性等非功能需求
- business_rule：业务约束、权限规则、状态流转
- ui_flow：页面流程、导航结构、信息架构

对每个识别到的块，输出：
- block_id：唯一标识（格式：B001, B002, ...）
- type：上述类型之一
- title：该块的标题或概要描述
- source_range：在原文中的位置范围（段落序号，如 [0, 15]）
- dependencies：该块引用或依赖的其他 block_id 列表

重要规则：
1. block_id 必须唯一，不能重复
2. source_range 表示段落序号范围 [start, end]，不同块之间不能重叠
3. dependencies 中引用的 block_id 必须是本次输出中存在的
4. 只做结构识别，不做内容理解
5. 输出纯 JSON，不要添加任何解释文字

输出格式为 JSON：
{
  "blocks": [
    {
      "block_id": "B001",
      "type": "product_overview",
      "title": "产品概述",
      "source_range": [0, 15],
      "dependencies": []
    }
  ]
}"""


CHAIN1_USER_PROMPT = """请分析以下 PRD 文档的结构，识别信息块并输出骨架索引。

文档内容（带段落编号）：

{doc_text}"""


CHAIN1_USER_PROMPT_LONG = """请分析以下 PRD 文档的结构，识别信息块并输出骨架索引。

注意：该文档较长（共 {total_paragraphs} 个段落），以下提供了前 2000 字内容和全部标题供你分析。请基于标题和前文内容推断完整的文档结构。

{summary_text}"""


CHAIN1_RETRY_PROMPT = """你上一次的输出存在以下校验错误，请修正后重新输出完整的 JSON：

错误信息：
{errors}

请严格遵守以下规则：
1. block_id 必须唯一
2. source_range 不能重叠
3. dependencies 引用的 block_id 必须存在于输出中
4. 输出纯 JSON

原始文档内容：

{doc_text}"""
