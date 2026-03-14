"""Conversation service - v2.0 deep interaction system.

Three conversation modes:
- interview: One-on-one chat with a virtual persona
- focus_group: Multi-persona discussion on a topic
- report_qa: Follow-up questions about report findings
"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import llm_call
from app.models import database as db_module
from app.models.database import Analysis, Conversation
from app.prompts.conversation_prompts import (
    INTERVIEW_SYSTEM_PROMPT,
    FOCUS_GROUP_PERSONA_PROMPT,
    REPORT_QA_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)


async def start_conversation(
    analysis_id: str,
    mode: str,
    persona_ids: list[str],
    topic: str | None = None,
) -> str:
    """Create a new conversation record.

    Returns:
        conversation_id
    """
    async with db_module._session_factory() as db:
        conversation = Conversation(
            analysis_id=analysis_id,
            mode=mode,
            persona_ids=persona_ids,
            topic=topic,
            messages=[],
        )
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        return conversation.id


async def send_message(conversation_id: str, user_content: str) -> list[dict]:
    """Send a user message and get response(s).

    Returns:
        List of response messages [{role, persona_id?, content}]
    """
    async with db_module._session_factory() as db:
        result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise ValueError("Conversation not found")

        # Load analysis data
        result = await db.execute(
            select(Analysis).where(Analysis.id == conversation.analysis_id)
        )
        analysis = result.scalar_one_or_none()
        if not analysis:
            raise ValueError("Analysis not found")

        # Add user message
        messages = conversation.messages or []
        messages.append({"role": "user", "content": user_content})

        # Generate response based on mode
        mode = conversation.mode
        persona_ids = conversation.persona_ids or []
        topic = conversation.topic

        if mode == "interview":
            responses = await _handle_interview(
                analysis, persona_ids, messages
            )
        elif mode == "focus_group":
            responses = await _handle_focus_group(
                analysis, persona_ids, topic, messages, user_content
            )
        elif mode == "report_qa":
            responses = await _handle_report_qa(
                analysis, messages
            )
        else:
            responses = [{"role": "assistant", "content": f"未知对话模式: {mode}"}]

        # Save responses
        messages.extend(responses)
        conversation.messages = messages
        await db.commit()

        return responses


async def get_conversation(conversation_id: str) -> dict:
    """Get a conversation record."""
    async with db_module._session_factory() as db:
        result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise ValueError("Conversation not found")

        return {
            "id": conversation.id,
            "analysis_id": conversation.analysis_id,
            "mode": conversation.mode,
            "persona_ids": conversation.persona_ids,
            "topic": conversation.topic,
            "messages": conversation.messages,
            "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
        }


async def list_conversations(analysis_id: str) -> list[dict]:
    """List all conversations for an analysis."""
    async with db_module._session_factory() as db:
        result = await db.execute(
            select(Conversation)
            .where(Conversation.analysis_id == analysis_id)
            .order_by(Conversation.created_at.desc())
        )
        conversations = result.scalars().all()

        return [
            {
                "id": c.id,
                "analysis_id": c.analysis_id,
                "mode": c.mode,
                "persona_ids": c.persona_ids,
                "topic": c.topic,
                "message_count": len(c.messages) if c.messages else 0,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in conversations
        ]


# --- Mode Handlers ---


async def _handle_interview(
    analysis: Analysis,
    persona_ids: list[str],
    messages: list[dict],
) -> list[dict]:
    """Handle one-on-one interview mode."""
    if not persona_ids:
        return [{"role": "assistant", "content": "未指定对话角色"}]

    persona_id = persona_ids[0]
    persona = _find_persona(analysis, persona_id)
    if not persona:
        return [{"role": "assistant", "content": f"角色 {persona_id} 未找到"}]

    # Find simulation data for this persona
    simulation = _find_simulation(analysis, persona_id)

    # Build system prompt
    dims = persona.get("dimensions", {})
    friction_points = simulation.get("friction_points", []) if simulation else []
    friction_summary = "\n".join(
        f"- [{fp.get('severity')}] {fp.get('description')}" for fp in friction_points
    ) if friction_points else "未发现明显问题"

    system_prompt = INTERVIEW_SYSTEM_PROMPT.format(
        name=persona["name"],
        age=persona["age"],
        occupation=persona["occupation"],
        background=persona["background"],
        tech_sensitivity=dims.get("tech_sensitivity", 50),
        patience_threshold=dims.get("patience_threshold", 50),
        pay_willingness=dims.get("pay_willingness", 50),
        alt_dependency=dims.get("alt_dependency", 50),
        narrative=simulation.get("narrative", "暂无体验记忆") if simulation else "暂无体验记忆",
        final_emotion=simulation.get("emotion_curve", [50])[-1] if simulation and simulation.get("emotion_curve") else 50,
        friction_summary=friction_summary,
    )

    # Build message history for LLM
    llm_messages = _build_llm_messages(system_prompt, messages)

    response = await llm_call(
        prompt=messages[-1]["content"],
        system_prompt=system_prompt,
        messages=llm_messages[:-1],  # Exclude the last user message (it's the prompt)
        temperature=0.7,
    )

    # llm_call returns a dict for json mode, string for text mode
    content = response if isinstance(response, str) else json.dumps(response, ensure_ascii=False)

    return [{"role": "assistant", "persona_id": persona_id, "content": content}]


async def _handle_focus_group(
    analysis: Analysis,
    persona_ids: list[str],
    topic: str | None,
    messages: list[dict],
    user_content: str,
) -> list[dict]:
    """Handle focus group discussion mode."""
    if not persona_ids or len(persona_ids) < 2:
        return [{"role": "assistant", "content": "焦点小组至少需要2个角色"}]

    topic = topic or "请分享你们对这个产品的看法"
    responses = []
    others_said_parts = []

    for pid in persona_ids:
        persona = _find_persona(analysis, pid)
        if not persona:
            continue

        simulation = _find_simulation(analysis, pid)

        # Build what others have said (including user and previous persona responses)
        others_said = f"产品经理说：{user_content}\n"
        if others_said_parts:
            others_said += "\n".join(others_said_parts)

        main_friction = "无明显问题"
        if simulation:
            fps = simulation.get("friction_points", [])
            if fps:
                main_friction = fps[0].get("description", "无明显问题")

        prompt = FOCUS_GROUP_PERSONA_PROMPT.format(
            name=persona["name"],
            age=persona["age"],
            occupation=persona["occupation"],
            attitude_tag=persona.get("attitude_tag", ""),
            narrative_summary=(simulation.get("narrative", "")[:200] + "...") if simulation else "暂无体验",
            final_emotion=simulation.get("emotion_curve", [50])[-1] if simulation and simulation.get("emotion_curve") else 50,
            main_friction=main_friction,
            others_said=others_said,
            topic=topic,
        )

        response = await llm_call(
            prompt=prompt,
            system_prompt=f"你是{persona['name']}，在参加焦点小组讨论。用真实自然的语气发言，1-3句话。不要输出 JSON。",
            temperature=0.8,
        )

        content = response if isinstance(response, str) else str(response)
        responses.append({
            "role": "assistant",
            "persona_id": pid,
            "content": content,
        })
        others_said_parts.append(f"{persona['name']}说：{content}")

    return responses


async def _handle_report_qa(
    analysis: Analysis,
    messages: list[dict],
) -> list[dict]:
    """Handle report Q&A mode."""
    report = analysis.report or {}
    personas_data = analysis.personas or {}
    simulations = analysis.simulations or []

    # Build context
    executive_summary = report.get("executive_summary", "")
    if not executive_summary:
        # Build from legacy fields
        bs_count = len(report.get("blind_spots", []))
        bn_count = len(report.get("bottlenecks", []))
        ar_count = len(report.get("assumption_risks", []))
        executive_summary = f"发现 {bs_count} 个盲区，{bn_count} 个瓶颈，{ar_count} 个假设风险。NPS 均值: {report.get('nps_average', 0)}"

    findings = []
    for bs in report.get("blind_spots", []):
        findings.append(f"[盲区] {bs.get('title')}: {bs.get('description')}")
    for bn in report.get("bottlenecks", []):
        findings.append(f"[瓶颈] {bn.get('title')}: {bn.get('description')}")
    for ar in report.get("assumption_risks", []):
        findings.append(f"[风险] {ar.get('assumption')}: {ar.get('if_wrong')}")
    findings_summary = "\n".join(findings) if findings else "暂无发现"

    persona_list = personas_data.get("personas", [])
    detailed_lines = []
    persona_map = {p["persona_id"]: p for p in persona_list}
    for sim in simulations[:8]:
        pname = persona_map.get(sim.get("persona_id", ""), {}).get("name", "未知")
        detailed_lines.append(
            f"- {pname}: NPS={sim.get('nps_score')}, 结果={sim.get('outcome')}, "
            f"场景={sim.get('scene', 'first_use')}, 摩擦点={len(sim.get('friction_points', []))}"
        )

    graph = analysis.graph or {}

    system_prompt = REPORT_QA_SYSTEM_PROMPT.format(
        executive_summary=executive_summary,
        findings_summary=findings_summary,
        persona_count=len(persona_list),
        simulation_count=len(simulations),
        node_count=len(graph.get("nodes", [])),
        conflict_count=len(graph.get("conflicts", [])),
        detailed_data="\n".join(detailed_lines) if detailed_lines else "无详细数据",
    )

    llm_messages = _build_llm_messages(system_prompt, messages)

    response = await llm_call(
        prompt=messages[-1]["content"],
        system_prompt=system_prompt,
        messages=llm_messages[:-1],
        temperature=0.5,
    )

    content = response if isinstance(response, str) else json.dumps(response, ensure_ascii=False)
    return [{"role": "assistant", "content": content}]


# --- Helpers ---


def _find_persona(analysis: Analysis, persona_id: str) -> dict | None:
    """Find a persona by ID from analysis data."""
    personas_data = analysis.personas or {}
    for p in personas_data.get("personas", []):
        if p.get("persona_id") == persona_id:
            return p
    return None


def _find_simulation(analysis: Analysis, persona_id: str, scene: str = None) -> dict | None:
    """Find simulation result for a persona."""
    simulations = analysis.simulations or []
    for s in simulations:
        if s.get("persona_id") == persona_id:
            if scene is None or s.get("scene") == scene:
                return s
    return None


def _build_llm_messages(system_prompt: str, messages: list[dict]) -> list[dict]:
    """Build LLM message history from conversation messages."""
    llm_messages = []
    for msg in messages:
        role = msg.get("role", "user")
        if role == "user":
            llm_messages.append({"role": "user", "content": msg["content"]})
        elif role == "assistant":
            llm_messages.append({"role": "assistant", "content": msg["content"]})
    return llm_messages
