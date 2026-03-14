"""Narrative simulation service - Chain 4: Multi-scene first-person experience simulation.

v2.0 enhancements:
- Multi-scenario simulation (first_use, deep_use, competitor, churn)
- Structured action logs per simulation step
- Action logs persisted to database
"""

import asyncio
import logging

from app.llm.client import llm_call
from app.models.schema import SimulationResult
from app.models import database as db_module
from app.models.database import ActionLog
from app.prompts.chain4_simulate import (
    CHAIN4_SYSTEM_PROMPT,
    CHAIN4_USER_PROMPT,
    CHAIN4_RETRY_PROMPT,
)
from app.prompts.chain4_scenes import (
    SCENE_CONTEXTS,
    ACTION_LOG_INSTRUCTION,
    get_scenes_for_persona,
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 2
VALID_OUTCOMES = {"completed", "churned", "confused", "evaluating", "inactive"}
VALID_SEVERITIES = {"high", "medium", "low"}
VALID_FRICTION_TYPES = {"功能缺失", "体验摩擦", "认知错位", "动机不足"}


async def run_simulation(
    graph: dict,
    personas: dict,
    analysis_id: str | None = None,
    progress_callback=None,
) -> list[dict]:
    """Run multi-scene narrative simulation for all personas concurrently.

    Args:
        graph: FullGraph dict from Chain 2.5
        personas: PersonaSet dict from Chain 3
        analysis_id: Analysis ID for persisting action logs
        progress_callback: Optional callback(progress, message, preview)

    Returns:
        List of SimulationResult dicts (one per persona per scene)
    """
    persona_list = personas.get("personas", [])
    core_paths = graph.get("core_paths", [])
    nodes = graph.get("nodes", [])

    if not persona_list:
        logger.warning("No personas to simulate")
        return []

    if not core_paths:
        logger.warning("No core paths for simulation")
        return []

    # Build simulation tasks: each persona may have multiple scenes
    node_map = {n["id"]: n for n in nodes}
    tasks = []
    task_info = []  # Track (persona_id, scene) for progress reporting

    for persona in persona_list:
        scenes = get_scenes_for_persona(persona.get("type", "core"))
        for scene in scenes:
            tasks.append(
                _simulate_persona(persona, core_paths, node_map, graph, scene, analysis_id)
            )
            task_info.append((persona["persona_id"], scene))

    total_tasks = len(tasks)
    if progress_callback:
        progress_callback(0.05, f"正在准备 {len(persona_list)} 个角色的 {total_tasks} 场仿真...")

    # Run all simulations concurrently
    completed = 0
    results = []
    for coro in asyncio.as_completed(tasks):
        try:
            result = await coro
            results.append(result)
        except Exception as e:
            logger.error(f"Simulation failed: {e}", exc_info=True)
            results.append(None)

        completed += 1
        if progress_callback:
            progress_callback(
                0.1 + 0.85 * (completed / total_tasks),
                f"仿真进度：{completed}/{total_tasks} 场完成",
                {"completed": completed, "total": total_tasks},
            )

    # Filter out failed simulations
    valid_results = [r for r in results if r is not None]

    if progress_callback:
        progress_callback(1.0, f"仿真完成：{len(valid_results)}/{total_tasks} 场",
                          {"completed": len(valid_results), "total": total_tasks})

    return valid_results


async def _simulate_persona(
    persona: dict,
    core_paths: list[dict],
    node_map: dict,
    graph: dict,
    scene: str,
    analysis_id: str | None = None,
) -> dict:
    """Simulate a single persona's experience in a specific scene."""
    # Select the most relevant path for this persona
    path = _select_primary_path(persona, core_paths)
    node_sequence = path.get("node_sequence", [])
    node_count = len(node_sequence)

    # Build descriptions
    path_description = _build_path_description(path, node_map)
    node_sequence_desc = _build_node_sequence_description(node_sequence, node_map)
    touchpoints_info = _build_touchpoints_info(path, node_map)
    risk_points_info = _build_risk_points_info(path, node_map)

    dims = persona.get("dimensions", {})

    # Get scene context
    scene_context = SCENE_CONTEXTS.get(scene, SCENE_CONTEXTS["first_use"])

    # Build system prompt with persona + scene context
    system_prompt = CHAIN4_SYSTEM_PROMPT.format(
        persona_name=persona["name"],
        persona_age=persona["age"],
        persona_occupation=persona["occupation"],
        persona_background=persona["background"],
        persona_motivation=persona["motivation"],
        persona_cognitive_model=persona["cognitive_model"],
        tech_sensitivity=dims.get("tech_sensitivity", 50),
        patience_threshold=dims.get("patience_threshold", 50),
        pay_willingness=dims.get("pay_willingness", 50),
        alt_dependency=dims.get("alt_dependency", 50),
        persona_attitude_tag=persona["attitude_tag"],
        path_description=path_description,
        node_count=node_count,
        persona_id=persona["persona_id"],
    )

    # Inject scene context and action log instruction into system prompt
    system_prompt = system_prompt.replace(
        "你即将第一次使用一个产品。",
        f"{scene_context}\n\n"
    )
    # Add action log instruction before the JSON format example
    system_prompt = system_prompt.replace(
        "输出纯 JSON",
        f"{ACTION_LOG_INSTRUCTION}\n\n输出纯 JSON"
    )
    # Update JSON format to include action_logs and scene
    system_prompt = system_prompt.replace(
        '"persona_id": "{persona_id}",',
        f'"persona_id": "{persona["persona_id"]}",\n  "scene": "{scene}",'
    )
    system_prompt = system_prompt.replace(
        '"willingness_to_return": {',
        '"action_logs": [...],\n  "willingness_to_return": {'
    )

    user_prompt = CHAIN4_USER_PROMPT.format(
        persona_name=persona["name"],
        path_name=path["name"],
        node_sequence_description=node_sequence_desc,
        touchpoints_info=touchpoints_info,
        risk_points_info=risk_points_info,
        expected_friction_points="\n".join(f"- {fp}" for fp in persona.get("expected_friction_points", [])),
        persona_attitude_tag=persona["attitude_tag"],
    )

    result = await llm_call(
        prompt=user_prompt,
        system_prompt=system_prompt,
        output_format="json",
        temperature=0.8,
        max_tokens=8192,
    )

    # Ensure persona_id and scene are set
    result["persona_id"] = persona["persona_id"]
    result["scene"] = scene

    # Validate and retry
    for attempt in range(MAX_RETRIES):
        errors = _validate_simulation(result, node_count)
        if not errors:
            break

        logger.warning(
            f"Chain 4 validation failed for {persona['persona_id']}:{scene} "
            f"(attempt {attempt + 1}): {errors}"
        )
        retry_prompt = CHAIN4_RETRY_PROMPT.format(
            errors="\n".join(f"- {e}" for e in errors),
            node_count=node_count,
            persona_name=persona["name"],
            persona_id=persona["persona_id"],
        )
        result = await llm_call(
            prompt=retry_prompt,
            system_prompt=system_prompt,
            output_format="json",
            temperature=0.6,
        )
        result["persona_id"] = persona["persona_id"]
        result["scene"] = scene

    # Ensure action_logs field exists (LLM may not always generate it)
    if "action_logs" not in result or not isinstance(result.get("action_logs"), list):
        result["action_logs"] = _generate_action_logs_from_narrative(result, scene)

    # Persist action logs to database
    if analysis_id:
        await _persist_action_logs(analysis_id, persona["persona_id"], scene, result.get("action_logs", []))

    # Validate with Pydantic
    sim_result = SimulationResult(**result)
    return sim_result.model_dump()


def _generate_action_logs_from_narrative(result: dict, scene: str) -> list[dict]:
    """Generate basic action logs from emotion curve when LLM doesn't provide them."""
    logs = []
    emotion_curve = result.get("emotion_curve", [])
    for i, emotion in enumerate(emotion_curve):
        logs.append({
            "step": i + 1,
            "action": "interact",
            "target": None,
            "emotion": emotion / 100.0 if emotion > 1 else emotion,
            "thought": "",
            "friction": None,
        })
    return logs


async def _persist_action_logs(
    analysis_id: str,
    persona_id: str,
    scene: str,
    action_logs: list[dict],
):
    """Save action log entries to the database."""
    try:
        async with db_module._session_factory() as db:
            for log_entry in action_logs:
                log = ActionLog(
                    analysis_id=analysis_id,
                    persona_id=persona_id,
                    step=log_entry.get("step", 0),
                    scene=scene,
                    action=log_entry.get("action", "unknown"),
                    target=log_entry.get("target"),
                    emotion=log_entry.get("emotion"),
                    thought=log_entry.get("thought"),
                    friction=log_entry.get("friction"),
                )
                db.add(log)
            await db.commit()
    except Exception as e:
        logger.error(f"Failed to persist action logs: {e}", exc_info=True)


def _select_primary_path(persona: dict, core_paths: list[dict]) -> dict:
    """Select the most relevant core path for a persona."""
    if not core_paths:
        return {"path_id": "default", "name": "默认路径", "node_sequence": [],
                "critical_touchpoints": [], "risk_points": []}

    ptype = persona.get("type", "core")

    if ptype == "core":
        return core_paths[0]

    # For adversarial personas, prefer paths with more risk points
    paths_with_risks = [(p, len(p.get("risk_points", []))) for p in core_paths]
    paths_with_risks.sort(key=lambda x: x[1], reverse=True)

    persona_num = 0
    pid = persona.get("persona_id", "")
    if pid.startswith("P"):
        try:
            persona_num = int(pid[1:])
        except ValueError:
            pass

    idx = persona_num % len(core_paths)
    return core_paths[idx]


def _build_path_description(path: dict, node_map: dict) -> str:
    """Build natural language description of a core path."""
    steps = []
    for nid in path.get("node_sequence", []):
        node = node_map.get(nid)
        if node:
            steps.append(f"{node['name']}（{node['description']}）")
        else:
            steps.append(nid)
    return " → ".join(steps)


def _build_node_sequence_description(node_sequence: list[str], node_map: dict) -> str:
    """Build numbered node sequence description."""
    lines = []
    for i, nid in enumerate(node_sequence, 1):
        node = node_map.get(nid)
        if node:
            lines.append(f"{i}. [{node['type']}] {node['name']}：{node['description']}")
        else:
            lines.append(f"{i}. {nid}")
    return "\n".join(lines)


def _build_touchpoints_info(path: dict, node_map: dict) -> str:
    """Build touchpoint information for the path."""
    lines = []
    for tid in path.get("critical_touchpoints", []):
        node = node_map.get(tid)
        if node:
            lines.append(f"- {node['name']}：{node['description']}")
    return "\n".join(lines) if lines else "无特别标注的关键触点"


def _build_risk_points_info(path: dict, node_map: dict) -> str:
    """Build risk point information for the path."""
    lines = []
    for rid in path.get("risk_points", []):
        node = node_map.get(rid)
        if node:
            lines.append(f"- {node['name']}：{node['description']}")
    return "\n".join(lines) if lines else "无特别标注的风险点"


def _validate_simulation(data: dict, expected_node_count: int) -> list[str]:
    """Validate Chain 4 simulation output."""
    errors = []

    for field in ("persona_id", "narrative", "emotion_curve", "outcome",
                  "nps_score", "nps_reason", "willingness_to_return"):
        if field not in data:
            errors.append(f"缺少 '{field}' 字段")

    if errors:
        return errors

    # Validate narrative
    if not data.get("narrative") or len(data["narrative"]) < 50:
        errors.append("narrative 叙事文本过短（应至少 50 字）")

    # Validate emotion_curve
    curve = data.get("emotion_curve", [])
    if not isinstance(curve, list):
        errors.append("emotion_curve 必须是数组")
    elif len(curve) != expected_node_count and expected_node_count > 0:
        errors.append(f"emotion_curve 长度 {len(curve)} 不等于路径节点数 {expected_node_count}")
    else:
        for i, val in enumerate(curve):
            if not isinstance(val, (int, float)) or val < 0 or val > 100:
                errors.append(f"emotion_curve[{i}] 值 {val} 超出 0-100 范围")
                break

    # Validate friction_points
    for fp in data.get("friction_points", []):
        if fp.get("severity") not in VALID_SEVERITIES:
            errors.append(f"friction_point severity '{fp.get('severity')}' 无效")
        if fp.get("type") not in VALID_FRICTION_TYPES:
            errors.append(f"friction_point type '{fp.get('type')}' 无效")
        for field in ("node_id", "description", "quote"):
            if not fp.get(field):
                errors.append(f"friction_point 缺少 {field}")

    # Validate outcome
    if data.get("outcome") not in VALID_OUTCOMES:
        errors.append(f"outcome '{data.get('outcome')}' 无效")

    # Validate nps_score
    nps = data.get("nps_score")
    if not isinstance(nps, (int, float)) or nps < 0 or nps > 10:
        errors.append(f"nps_score {nps} 超出 0-10 范围")

    # Validate willingness_to_return
    wtr = data.get("willingness_to_return")
    if not isinstance(wtr, dict):
        errors.append("willingness_to_return 必须是对象")
    else:
        if "will_return" not in wtr:
            errors.append("willingness_to_return 缺少 will_return")
        if not wtr.get("reason"):
            errors.append("willingness_to_return 缺少 reason")

    return errors
