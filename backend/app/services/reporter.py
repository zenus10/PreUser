"""Report generation service - Chain 5 v2.0: Multi-round agent report generation.

Borrowing MiroFish's ReACT pattern:
  Round 1: Generate report outline
  Round 2: Generate each section with reasoning trace
  Round 3: Review all sections and generate executive summary + structured data
"""

import json
import logging
from collections import Counter

from app.llm.client import llm_call
from app.models.schema import TestReport, ReportSection
from app.prompts.chain5_sections import (
    OUTLINE_SYSTEM_PROMPT,
    OUTLINE_USER_PROMPT,
    SECTION_SYSTEM_PROMPT,
    SECTION_USER_PROMPTS,
    REVIEW_SYSTEM_PROMPT,
    REVIEW_USER_PROMPT,
)
from app.prompts.chain5_report import (
    CHAIN5_SYSTEM_PROMPT,
    CHAIN5_USER_PROMPT,
    CHAIN5_RETRY_PROMPT,
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 2

# Standard section titles in order
SECTION_TITLES = [
    "Executive Summary",
    "用户画像洞察",
    "功能体验分析",
    "设计盲区发现",
    "假设风险矩阵",
    "行动建议",
]


async def generate_report(
    graph: dict,
    personas: dict,
    simulations: list[dict],
    analysis_id: str | None = None,
    progress_callback=None,
) -> dict:
    """Generate multi-round agent report.

    Args:
        graph: FullGraph dict
        personas: PersonaSet dict
        simulations: List of SimulationResult dicts
        analysis_id: Analysis ID for logging
        progress_callback: Optional callback(progress, message, preview)

    Returns:
        TestReport as dict (with sections, executive_summary, and legacy fields)
    """
    if progress_callback:
        progress_callback(0.05, "正在聚合仿真数据...")

    # Step 1: Data aggregation (pure computation, no LLM)
    aggregated = _aggregate_data(simulations, personas)

    if progress_callback:
        progress_callback(0.1, f"数据聚合完成，模拟 NPS: {aggregated['nps_average']:.1f}")

    # Step 2: Round 1 - Generate outline
    if progress_callback:
        progress_callback(0.15, "Round 1/3: 正在生成报告大纲...")

    outline = await _round1_outline(aggregated, personas, simulations, graph)
    section_plan = outline.get("sections", [])

    if not section_plan or len(section_plan) < 6:
        # Fallback to standard sections if outline generation fails
        section_plan = [{"title": t, "summary": "", "key_data_points": []} for t in SECTION_TITLES]

    logger.info(f"Report outline: {len(section_plan)} sections planned")

    # Step 3: Round 2 - Generate each section
    sections: list[dict] = []
    total_sections = len(section_plan)

    for i, plan in enumerate(section_plan):
        title = plan.get("title", SECTION_TITLES[i] if i < len(SECTION_TITLES) else f"章节{i+1}")
        if progress_callback:
            progress_callback(
                0.2 + 0.5 * (i / total_sections),
                f"Round 2/3: 正在生成「{title}」({i+1}/{total_sections})..."
            )

        section = await _round2_section(
            section_index=i + 1,
            section_title=title,
            section_summary=plan.get("summary", ""),
            aggregated=aggregated,
            graph=graph,
            personas=personas,
            simulations=simulations,
            previous_sections=sections,
        )
        sections.append(section)

    logger.info(f"Generated {len(sections)} report sections")

    # Step 4: Round 3 - Review and generate executive summary + structured data
    if progress_callback:
        progress_callback(0.75, "Round 3/3: 正在审查报告一致性并生成执行摘要...")

    review_result = await _round3_review(aggregated, sections, personas)

    # Merge everything into final report
    report = {
        "sections": sections,
        "executive_summary": review_result.get("executive_summary", ""),
        "blind_spots": review_result.get("blind_spots", []),
        "bottlenecks": review_result.get("bottlenecks", []),
        "assumption_risks": review_result.get("assumption_risks", []),
        "nps_average": aggregated["nps_average"],
        "satisfaction_matrix": aggregated["satisfaction_matrix"],
        "churn_attribution": aggregated["churn_attribution"],
    }

    if progress_callback:
        bs = len(report["blind_spots"])
        bn = len(report["bottlenecks"])
        ar = len(report["assumption_risks"])
        progress_callback(1.0, f"报告生成完成：{bs} 个盲区，{bn} 个瓶颈，{ar} 个假设风险",
                          {"blind_spots": bs, "bottlenecks": bn, "assumption_risks": ar})

    # Validate with Pydantic
    test_report = TestReport(**report)
    return test_report.model_dump()


async def _round1_outline(
    aggregated: dict,
    personas: dict,
    simulations: list[dict],
    graph: dict,
) -> dict:
    """Round 1: Generate report outline."""
    persona_list = personas.get("personas", [])
    core_count = sum(1 for p in persona_list if p.get("type") == "core")
    adversarial_count = len(persona_list) - core_count

    # Top 3 friction summary
    friction_stats = aggregated.get("friction_stats", [])[:3]
    top_friction_lines = []
    for fs in friction_stats:
        affected = len(fs.get("affected_personas", []))
        top_friction_lines.append(
            f"  - [{fs.get('severity', '?')}] {fs.get('description', '?')} (影响 {affected} 人)"
        )
    top_friction_summary = "\n".join(top_friction_lines) if top_friction_lines else "  无摩擦点数据"

    user_prompt = OUTLINE_USER_PROMPT.format(
        persona_count=len(persona_list),
        core_count=core_count,
        adversarial_count=adversarial_count,
        simulation_count=len(simulations),
        nps_average=aggregated["nps_average"],
        completion_rate=aggregated.get("completion_rate", 0),
        churn_rate=aggregated.get("churned_count", 0) / max(aggregated.get("total_count", 1), 1),
        conflict_count=len(graph.get("conflicts", [])),
        top_friction_summary=top_friction_summary,
    )

    try:
        result = await llm_call(
            prompt=user_prompt,
            system_prompt=OUTLINE_SYSTEM_PROMPT,
            output_format="json",
            temperature=0.4,
        )
        return result
    except Exception as e:
        logger.error(f"Round 1 outline generation failed: {e}")
        return {"sections": [{"title": t, "summary": "", "key_data_points": []} for t in SECTION_TITLES]}


async def _round2_section(
    section_index: int,
    section_title: str,
    section_summary: str,
    aggregated: dict,
    graph: dict,
    personas: dict,
    simulations: list[dict],
    previous_sections: list[dict],
) -> dict:
    """Round 2: Generate a single report section with reasoning trace."""
    system_prompt = SECTION_SYSTEM_PROMPT.format(
        section_index=section_index,
        section_title=section_title,
        section_summary=section_summary,
    )

    # Build section-specific data context
    user_prompt = _build_section_user_prompt(
        section_title, aggregated, graph, personas, simulations, previous_sections
    )

    try:
        result = await llm_call(
            prompt=user_prompt,
            system_prompt=system_prompt,
            output_format="json",
            temperature=0.5,
            max_tokens=8192,
        )

        # Ensure required fields
        return {
            "title": result.get("title", section_title),
            "content": result.get("content", ""),
            "reasoning_trace": result.get("reasoning_trace", ""),
            "data_references": result.get("data_references", []),
        }
    except Exception as e:
        logger.error(f"Section generation failed for '{section_title}': {e}")
        return {
            "title": section_title,
            "content": f"章节生成失败: {str(e)}",
            "reasoning_trace": "",
            "data_references": [],
        }


async def _round3_review(
    aggregated: dict,
    sections: list[dict],
    personas: dict,
) -> dict:
    """Round 3: Review all sections and generate executive summary + structured data."""
    # Build sections content
    sections_text = []
    for s in sections:
        sections_text.append(f"### {s['title']}\n{s['content']}\n")
    all_sections_content = "\n---\n".join(sections_text)

    valid_persona_ids = [p["persona_id"] for p in personas.get("personas", [])]

    user_prompt = REVIEW_USER_PROMPT.format(
        nps_average=aggregated["nps_average"],
        completion_rate=aggregated.get("completion_rate", 0),
        churn_rate=aggregated.get("churned_count", 0) / max(aggregated.get("total_count", 1), 1),
        all_sections_content=all_sections_content,
        valid_persona_ids=json.dumps(valid_persona_ids, ensure_ascii=False),
    )

    try:
        result = await llm_call(
            prompt=user_prompt,
            system_prompt=REVIEW_SYSTEM_PROMPT,
            output_format="json",
            temperature=0.4,
            max_tokens=8192,
        )

        # Validate structured data
        _validate_and_fix_review(result, valid_persona_ids)
        return result
    except Exception as e:
        logger.error(f"Round 3 review failed: {e}")
        # Fallback: use legacy single-round generation
        return await _fallback_legacy_report(aggregated, sections, personas)


async def _fallback_legacy_report(
    aggregated: dict,
    sections: list[dict],
    personas: dict,
) -> dict:
    """Fallback to v1.0 style single-round report if multi-round fails."""
    logger.warning("Falling back to legacy single-round report generation")

    prompt_data = _build_legacy_prompt_data(aggregated, sections, personas)
    user_prompt = CHAIN5_USER_PROMPT.format(**prompt_data)

    result = await llm_call(
        prompt=user_prompt,
        system_prompt=CHAIN5_SYSTEM_PROMPT,
        output_format="json",
        temperature=0.5,
        max_tokens=8192,
    )

    result["executive_summary"] = ""
    return result


def _build_section_user_prompt(
    section_title: str,
    aggregated: dict,
    graph: dict,
    personas: dict,
    simulations: list[dict],
    previous_sections: list[dict],
) -> str:
    """Build the user prompt for a specific section with relevant data."""
    persona_list = personas.get("personas", [])
    persona_map = {p["persona_id"]: p for p in persona_list}

    template = SECTION_USER_PROMPTS.get(section_title)
    if not template:
        # Generic fallback
        return f"请生成「{section_title}」章节。\n\n可用数据：\n{json.dumps(aggregated, ensure_ascii=False, indent=2)[:3000]}"

    if section_title == "Executive Summary":
        prev_summary = "\n".join(
            f"- {s['title']}: {s['content'][:200]}..." for s in previous_sections
        )
        data_context = (
            f"NPS 均值: {aggregated['nps_average']}\n"
            f"完成率: {aggregated.get('completion_rate', 0):.0%}\n"
            f"流失率: {aggregated.get('churned_count', 0)}/{aggregated.get('total_count', 1)}\n"
        )
        return template.format(
            previous_sections_summary=prev_summary,
            data_context=data_context,
        )

    elif section_title == "用户画像洞察":
        persona_data = "\n".join(
            f"- {p['name']}({p['type']}): {p['attitude_tag']}, "
            f"技术={p['dimensions']['tech_sensitivity']}, "
            f"耐心={p['dimensions']['patience_threshold']}"
            for p in persona_list
        )
        sim_summary = "\n".join(
            f"- {persona_map.get(s['persona_id'], {}).get('name', s['persona_id'])}: "
            f"结果={s.get('outcome')}, NPS={s.get('nps_score')}, "
            f"场景={s.get('scene', 'first_use')}"
            for s in simulations
        )
        return template.format(persona_data=persona_data, simulation_summary=sim_summary)

    elif section_title == "功能体验分析":
        friction_lines = []
        for fs in aggregated.get("friction_stats", [])[:10]:
            affected = len(fs.get("affected_personas", []))
            friction_lines.append(
                f"- [{fs['severity']}] {fs.get('description', '')} "
                f"(影响 {affected} 人, 节点: {fs.get('node_id', '')})"
            )
        friction_data = "\n".join(friction_lines) if friction_lines else "无摩擦点数据"

        sat_lines = []
        for pname, stats in aggregated.get("satisfaction_matrix", {}).items():
            sat_lines.append(f"- {pname}: NPS={stats.get('nps_score')}, friction={stats.get('friction_count')}")
        satisfaction_data = "\n".join(sat_lines) if sat_lines else "无满意度数据"

        emotion_lines = []
        for s in simulations[:5]:
            pname = persona_map.get(s['persona_id'], {}).get('name', s['persona_id'])
            curve = s.get("emotion_curve", [])
            emotion_lines.append(f"- {pname}: {curve[:8]}...")
        emotion_data = "\n".join(emotion_lines) if emotion_lines else "无情绪数据"

        return template.format(
            friction_data=friction_data,
            satisfaction_data=satisfaction_data,
            emotion_data=emotion_data,
        )

    elif section_title == "设计盲区发现":
        conflicts = graph.get("conflicts", [])
        conflict_lines = [
            f"- [{c['severity']}] {c['type']}: {c['description']}" for c in conflicts
        ]
        conflict_data = "\n".join(conflict_lines) if conflict_lines else "无图谱冲突"

        # Find anomalies: personas who churned or were confused
        anomalies = []
        for s in simulations:
            if s.get("outcome") in ("churned", "confused"):
                pname = persona_map.get(s['persona_id'], {}).get('name', s['persona_id'])
                anomalies.append(f"- {pname}({s.get('scene', 'first_use')}): {s.get('outcome')}, NPS={s.get('nps_score')}")
        anomaly_data = "\n".join(anomalies) if anomalies else "无异常行为"

        feedback_lines = []
        for s in simulations[:8]:
            pname = persona_map.get(s['persona_id'], {}).get('name', s['persona_id'])
            feedback_lines.append(f"- {pname}: {s.get('nps_reason', '')}")
        feedback_data = "\n".join(feedback_lines) if feedback_lines else "无反馈数据"

        return template.format(
            conflict_data=conflict_data,
            anomaly_data=anomaly_data,
            feedback_data=feedback_data,
        )

    elif section_title == "假设风险矩阵":
        counter_signals = []
        for s in simulations:
            if s.get("nps_score", 10) <= 4:
                pname = persona_map.get(s['persona_id'], {}).get('name', s['persona_id'])
                counter_signals.append(f"- {pname}: NPS={s.get('nps_score')}, {s.get('nps_reason', '')}")
        counter_text = "\n".join(counter_signals) if counter_signals else "无反常信号"

        churn_lines = [f"- {k}: {v}%" for k, v in aggregated.get("churn_attribution", {}).items()]
        churn_data = "\n".join(churn_lines) if churn_lines else "无流失数据"

        return template.format(counter_signals=counter_text, churn_data=churn_data)

    elif section_title == "行动建议":
        all_findings = "\n".join(
            f"### {s['title']}\n{s['content'][:500]}..." for s in previous_sections
        )
        return template.format(all_findings=all_findings)

    # Default fallback
    return f"请生成「{section_title}」章节。"


def _validate_and_fix_review(result: dict, valid_persona_ids: list[str]):
    """Validate and fix the review round output."""
    # Ensure all required arrays exist
    for key in ("blind_spots", "bottlenecks", "assumption_risks"):
        if key not in result or not isinstance(result[key], list):
            result[key] = []

    # Fix blind_spots
    for bs in result.get("blind_spots", []):
        if "description" not in bs:
            bs["description"] = bs.get("title", "")
        if "affected_personas" not in bs or not isinstance(bs.get("affected_personas"), list):
            bs["affected_personas"] = []
        if not isinstance(bs.get("evidence"), list):
            bs["evidence"] = [bs["evidence"]] if bs.get("evidence") else []
        if "recommendation" not in bs:
            bs["recommendation"] = ""

    # Fix bottleneck severity values
    for bn in result.get("bottlenecks", []):
        if bn.get("severity") not in ("high", "medium", "low"):
            bn["severity"] = "medium"
        if not isinstance(bn.get("affected_count"), (int, float)):
            bn["affected_count"] = 1
        if not isinstance(bn.get("quotes"), list):
            bn["quotes"] = []
        if "stage" not in bn:
            bn["stage"] = ""

    # Fix assumption_risks
    for ar in result.get("assumption_risks", []):
        # LLM sometimes uses "assumption_id" or "assumption_text" instead of "assumption"
        if "assumption" not in ar:
            ar["assumption"] = ar.get("assumption_text", ar.get("assumption_id", ""))
        if ar.get("risk_level") not in ("high", "medium", "low"):
            ar["risk_level"] = "medium"
        if "counter_evidence" not in ar:
            ar["counter_evidence"] = ""
        if "if_wrong" not in ar:
            ar["if_wrong"] = ""


def _build_legacy_prompt_data(aggregated: dict, sections: list[dict], personas: dict) -> dict:
    """Build prompt data for fallback legacy report generation."""
    churn_lines = [f"  - {k}: {v}%" for k, v in aggregated.get("churn_attribution", {}).items()]
    churn_attribution_text = "\n".join(churn_lines) if churn_lines else "  无流失数据"

    sat_lines = []
    for pname, stats in aggregated.get("satisfaction_matrix", {}).items():
        sat_lines.append(f"  - {pname}: NPS={stats.get('nps_score', 0)}, friction={stats.get('friction_count', 0)}")
    satisfaction_summary = "\n".join(sat_lines) if sat_lines else "  无满意度数据"

    sections_text = "\n---\n".join(f"### {s['title']}\n{s['content'][:300]}..." for s in sections)

    return {
        "nps_average": aggregated["nps_average"],
        "completion_rate": aggregated.get("completion_rate", 0),
        "completed_count": aggregated.get("completed_count", 0),
        "total_count": aggregated.get("total_count", 0),
        "churn_rate": aggregated.get("churned_count", 0) / max(aggregated.get("total_count", 1), 1),
        "churned_count": aggregated.get("churned_count", 0),
        "churn_attribution_text": churn_attribution_text,
        "satisfaction_summary": satisfaction_summary,
        "conflicts_text": sections_text[:500],
        "simulations_summary": "见上方各章节内容",
        "friction_summary": "见上方各章节内容",
    }


def _aggregate_data(simulations: list[dict], personas: dict) -> dict:
    """Aggregate simulation data for statistics (pure computation, no LLM)."""
    if not simulations:
        return {
            "nps_average": 0.0,
            "satisfaction_matrix": {},
            "churn_attribution": {},
            "completion_rate": 0.0,
            "completed_count": 0,
            "churned_count": 0,
            "total_count": 0,
            "friction_stats": [],
            "outcome_distribution": {},
        }

    total = len(simulations)

    # NPS average
    nps_scores = [s.get("nps_score", 0) for s in simulations]
    nps_average = sum(nps_scores) / total if total > 0 else 0.0

    # Outcome distribution
    outcomes = Counter(s.get("outcome", "unknown") for s in simulations)
    completed_count = outcomes.get("completed", 0)
    churned_count = outcomes.get("churned", 0)

    # Churn attribution
    churn_friction_types = Counter()
    for sim in simulations:
        if sim.get("outcome") in ("churned", "confused"):
            for fp in sim.get("friction_points", []):
                churn_friction_types[fp.get("type", "未知")] += 1

    total_churn_frictions = sum(churn_friction_types.values())
    churn_attribution = {}
    if total_churn_frictions > 0:
        for ftype, count in churn_friction_types.items():
            churn_attribution[ftype] = round(count / total_churn_frictions * 100, 1)
    else:
        churn_attribution = {"无流失": 100.0}

    # Satisfaction matrix
    persona_map = {p["persona_id"]: p for p in personas.get("personas", [])}
    satisfaction_matrix = {}
    for sim in simulations:
        pid = sim.get("persona_id", "")
        pname = persona_map.get(pid, {}).get("name", pid)
        scene = sim.get("scene", "first_use")
        key = f"{pname}({scene})" if scene != "first_use" else pname
        satisfaction_matrix[key] = {
            "nps_score": sim.get("nps_score", 0),
            "outcome": sim.get("outcome", "unknown"),
            "friction_count": len(sim.get("friction_points", [])),
        }

    # Friction point statistics
    all_frictions = []
    for sim in simulations:
        for fp in sim.get("friction_points", []):
            all_frictions.append({
                **fp,
                "persona_id": sim.get("persona_id", ""),
                "scene": sim.get("scene", "first_use"),
            })

    friction_by_node = {}
    for fp in all_frictions:
        nid = fp.get("node_id", "unknown")
        if nid not in friction_by_node:
            friction_by_node[nid] = {
                "node_id": nid,
                "type": fp.get("type", ""),
                "description": fp.get("description", ""),
                "severity": fp.get("severity", "low"),
                "affected_personas": [],
                "quotes": [],
            }
        friction_by_node[nid]["affected_personas"].append(fp.get("persona_id", ""))
        if fp.get("quote"):
            friction_by_node[nid]["quotes"].append(fp["quote"])

    friction_stats = sorted(
        friction_by_node.values(),
        key=lambda x: len(x["affected_personas"]),
        reverse=True,
    )

    return {
        "nps_average": round(nps_average, 1),
        "satisfaction_matrix": satisfaction_matrix,
        "churn_attribution": churn_attribution,
        "completion_rate": completed_count / total if total > 0 else 0.0,
        "completed_count": completed_count,
        "churned_count": churned_count,
        "total_count": total,
        "friction_stats": friction_stats,
        "outcome_distribution": dict(outcomes),
    }
