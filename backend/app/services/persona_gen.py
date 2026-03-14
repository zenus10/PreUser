"""Persona generation service - Chain 3: Generate virtual user personas from knowledge graph."""

import json
import logging

from app.llm.client import llm_call
from app.models.schema import PersonaSet, Persona
from app.prompts.chain3_persona import (
    CHAIN3_SYSTEM_PROMPT,
    CHAIN3_USER_PROMPT,
    CHAIN3_CORE_PROMPT,
    CHAIN3_ADVERSARIAL_PROMPT,
    CHAIN3_RETRY_PROMPT,
    CHAIN3_SUPPLEMENT_PROMPT,
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 2
REQUIRED_ADVERSARIAL_TYPES = {"cold", "resistant", "misuser"}
VALID_PERSONA_TYPES = {"core", "cold", "resistant", "misuser"}


async def generate_personas(
    graph: dict,
    progress_callback=None,
) -> dict:
    """Generate virtual user personas from the knowledge graph.

    Args:
        graph: FullGraph dict from Chain 2.5
        progress_callback: Optional callback(progress, message, preview)

    Returns:
        PersonaSet as dict
    """
    if progress_callback:
        progress_callback(0.1, "正在分析图谱中的角色信息...")

    # Extract relevant data from graph
    roles_json, touchpoints_json, paths_json, conflicts_json = _extract_graph_info(graph)

    if progress_callback:
        progress_callback(0.2, "正在生成虚拟用户画像...")

    # Step 1: Generate core personas
    core_prompt = CHAIN3_CORE_PROMPT.format(
        roles_json=roles_json,
        paths_json=paths_json,
        conflicts_json=conflicts_json,
        touchpoints_json=touchpoints_json,
    )

    core_result = await llm_call(
        prompt=core_prompt,
        system_prompt=CHAIN3_SYSTEM_PROMPT,
        output_format="json",
        temperature=0.7,
        max_tokens=8192,
    )

    if progress_callback:
        progress_callback(0.4, "核心画像生成完成，正在生成对抗性画像...")

    # Determine start_id for adversarial personas
    core_personas = core_result.get("personas", [])
    start_num = len(core_personas) + 1
    start_id = f"P{start_num:03d}"

    # Step 2: Generate adversarial personas
    adv_prompt = CHAIN3_ADVERSARIAL_PROMPT.format(
        start_id=start_id,
        roles_json=roles_json,
        paths_json=paths_json,
        conflicts_json=conflicts_json,
        touchpoints_json=touchpoints_json,
    )

    adv_result = await llm_call(
        prompt=adv_prompt,
        system_prompt=CHAIN3_SYSTEM_PROMPT,
        output_format="json",
        temperature=0.7,
        max_tokens=8192,
    )

    # Merge results
    adv_personas = adv_result.get("personas", [])
    result = {"personas": core_personas + adv_personas}

    # Validate and retry
    for attempt in range(MAX_RETRIES):
        errors = _validate_personas(result)
        if not errors:
            break

        logger.warning(f"Chain 3 validation failed (attempt {attempt + 1}): {errors}")
        if progress_callback:
            progress_callback(0.5 + attempt * 0.1, f"校验失败，正在重试 ({attempt + 1}/{MAX_RETRIES})...")

        retry_prompt = CHAIN3_RETRY_PROMPT.format(
            errors="\n".join(f"- {e}" for e in errors),
            roles_json=roles_json,
            paths_json=paths_json,
        )
        result = await llm_call(
            prompt=retry_prompt,
            system_prompt=CHAIN3_SYSTEM_PROMPT,
            output_format="json",
            temperature=0.5,
        )

    if progress_callback:
        progress_callback(0.7, "正在检查对抗性画像完整性...")

    # Check for missing adversarial types and supplement if needed
    result = await _ensure_adversarial_coverage(result, roles_json, paths_json)

    if progress_callback:
        persona_count = len(result.get("personas", []))
        types = {}
        for p in result.get("personas", []):
            t = p.get("type", "unknown")
            types[t] = types.get(t, 0) + 1
        progress_callback(1.0, f"画像生成完成：{persona_count} 个角色",
                          {"persona_count": persona_count, "type_distribution": types})

    # Validate with Pydantic
    persona_set = PersonaSet(**result)
    return persona_set.model_dump()


def _extract_graph_info(graph: dict) -> tuple[str, str, str, str]:
    """Extract roles, touchpoints, paths, and conflicts from graph for prompting."""
    nodes = graph.get("nodes", [])

    roles = [n for n in nodes if n.get("type") == "role"]
    touchpoints = [n for n in nodes if n.get("type") == "touchpoint"]
    core_paths = graph.get("core_paths", [])
    conflicts = graph.get("conflicts", [])

    roles_json = json.dumps(roles, ensure_ascii=False, indent=2)
    touchpoints_json = json.dumps(touchpoints, ensure_ascii=False, indent=2)
    paths_json = json.dumps(core_paths, ensure_ascii=False, indent=2)
    conflicts_json = json.dumps(conflicts, ensure_ascii=False, indent=2)

    return roles_json, touchpoints_json, paths_json, conflicts_json


def _validate_personas(data: dict) -> list[str]:
    """Validate Chain 3 persona generation output."""
    errors = []

    if "personas" not in data:
        errors.append("缺少 'personas' 字段")
        return errors

    personas = data["personas"]
    if not isinstance(personas, list) or len(personas) == 0:
        errors.append("'personas' 必须是非空数组")
        return errors

    seen_ids = set()
    for i, p in enumerate(personas):
        pid = p.get("persona_id", "")
        if not pid:
            errors.append(f"第 {i+1} 个画像缺少 persona_id")
        elif pid in seen_ids:
            errors.append(f"重复的 persona_id: {pid}")
        seen_ids.add(pid)

        # Check required fields
        for field in ("name", "age", "occupation", "type", "background",
                      "motivation", "attitude_tag", "cognitive_model"):
            if not p.get(field):
                errors.append(f"画像 {pid} 缺少 {field}")

        # Check type validity
        ptype = p.get("type", "")
        if ptype not in VALID_PERSONA_TYPES:
            errors.append(f"画像 {pid} 的 type '{ptype}' 无效，必须是 core/cold/resistant/misuser 之一")

        # Check dimensions
        dims = p.get("dimensions")
        if not isinstance(dims, dict):
            errors.append(f"画像 {pid} 缺少 dimensions 对象")
        else:
            for dim_name in ("tech_sensitivity", "patience_threshold", "pay_willingness", "alt_dependency"):
                val = dims.get(dim_name)
                if val is None:
                    errors.append(f"画像 {pid} 的 dimensions 缺少 {dim_name}")
                elif not isinstance(val, (int, float)) or val < 0 or val > 100:
                    errors.append(f"画像 {pid} 的 {dim_name} 值 {val} 超出 0-100 范围")

        # Check expected_friction_points
        efp = p.get("expected_friction_points")
        if not isinstance(efp, list):
            errors.append(f"画像 {pid} 的 expected_friction_points 必须是数组")

    return errors


async def _ensure_adversarial_coverage(
    result: dict,
    roles_json: str,
    paths_json: str,
) -> dict:
    """Check if all adversarial types are present, supplement if missing."""
    personas = result.get("personas", [])
    present_types = {p.get("type") for p in personas}
    missing = REQUIRED_ADVERSARIAL_TYPES - present_types

    if not missing:
        return result

    logger.info(f"Missing adversarial types: {missing}, generating supplement...")

    # Find max persona_id number
    max_num = 0
    for p in personas:
        pid = p.get("persona_id", "")
        if pid.startswith("P"):
            try:
                num = int(pid[1:])
                max_num = max(max_num, num)
            except ValueError:
                pass

    supplement_prompt = CHAIN3_SUPPLEMENT_PROMPT.format(
        missing_types="、".join(missing),
        max_id=f"P{max_num:03d}",
        roles_json=roles_json,
        paths_json=paths_json,
    )

    supplement = await llm_call(
        prompt=supplement_prompt,
        system_prompt=CHAIN3_SYSTEM_PROMPT,
        output_format="json",
        temperature=0.7,
    )

    new_personas = supplement.get("personas", [])
    if new_personas:
        result["personas"].extend(new_personas)
        logger.info(f"Supplemented {len(new_personas)} adversarial personas")

    return result


async def generate_custom_persona(description: str, existing_personas: dict | None = None) -> dict:
    """Generate a structured persona from a natural language description.

    Args:
        description: User's natural language description of the persona
        existing_personas: Existing personas dict for ID numbering

    Returns:
        Persona dict
    """
    max_num = 0
    if existing_personas:
        for p in existing_personas.get("personas", []):
            pid = p.get("persona_id", "")
            if pid.startswith("P"):
                try:
                    num = int(pid[1:])
                    max_num = max(max_num, num)
                except ValueError:
                    pass

    next_id = f"P{max_num + 1:03d}"

    prompt = f"""请根据以下用户描述，生成一个结构化的虚拟用户画像。

用户描述：{description}

输出一个 JSON 对象，格式如下：
{{
  "persona_id": "{next_id}",
  "name": "中文姓名",
  "age": 年龄数字,
  "occupation": "职业",
  "type": "core 或 cold 或 resistant 或 misuser",
  "background": "背景描述",
  "motivation": "使用动机",
  "attitude_tag": "一句话态度标签",
  "dimensions": {{
    "tech_sensitivity": 0-100,
    "patience_threshold": 0-100,
    "pay_willingness": 0-100,
    "alt_dependency": 0-100
  }},
  "cognitive_model": "对产品的理解模型",
  "expected_friction_points": ["预期摩擦点1", "预期摩擦点2"]
}}"""

    result = await llm_call(
        prompt=prompt,
        system_prompt="你是一个用户研究专家。根据描述生成结构化用户画像。输出纯 JSON。",
        output_format="json",
        temperature=0.6,
    )

    result["persona_id"] = next_id
    persona = Persona(**result)
    return persona.model_dump()
