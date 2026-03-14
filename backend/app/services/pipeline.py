"""Async pipeline - orchestrates the full analysis pipeline with checkpoint support."""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import llm_call
from app.llm.output_parser import validate_block_ids, validate_source_ranges
from app.models import database as db_module
from app.models.database import Project, Analysis
from app.models.schema import DocumentSkeleton, ProjectStatus, AnalysisCheckpoints
from app.prompts.chain1_structure import (
    CHAIN1_SYSTEM_PROMPT,
    CHAIN1_USER_PROMPT,
    CHAIN1_USER_PROMPT_LONG,
    CHAIN1_RETRY_PROMPT,
)
from app.services.parser import parse_document, extract_headers_summary
from app.services.graph_builder import build_graph
from app.services.persona_gen import generate_personas
from app.services.simulator import run_simulation
from app.services.reporter import generate_report
from app.services.checkpoint import (
    load_checkpoints,
    save_checkpoint,
    save_stage_output,
    load_stage_output,
    get_resume_stage,
)

logger = logging.getLogger(__name__)

# In-memory progress store (replace with Redis in production)
_progress: dict[str, dict] = {}

LONG_DOC_THRESHOLD = 8000  # chars
MAX_RETRIES = 2


def get_progress(project_id: str) -> dict | None:
    """Get current pipeline progress for a project."""
    return _progress.get(project_id)


async def run_parsing_pipeline(project_id: str, content: bytes, filename: str):
    """Run the full pipeline with checkpoint support.

    If a previous analysis exists with checkpoints, resumes from the last successful stage.
    """
    try:
        # ========== Stage 1: Document Parsing + Chain 1 ==========
        _update_progress(project_id, "parsing", 0, 0.0, "正在解析文档...")

        # Step 1: Parse document to extract text
        doc_data = parse_document(content, filename)
        paragraphs = doc_data["paragraphs"]
        page_count = doc_data["page_count"]

        _update_progress(project_id, "parsing", 0, 0.3, f"文档解析完成，共 {len(paragraphs)} 个段落")

        # Save doc_text and page_count to project
        async with db_module._session_factory() as db:
            result = await db.execute(select(Project).where(Project.id == project_id))
            project = result.scalar_one()
            project.doc_text = doc_data["text"]
            project.page_count = page_count
            project.status = ProjectStatus.PARSING
            await db.commit()

        # Create analysis record
        async with db_module._session_factory() as db:
            analysis = Analysis(
                project_id=project_id,
                version=1,
                status="running",
                checkpoints=AnalysisCheckpoints().model_dump(),
            )
            db.add(analysis)
            await db.commit()
            await db.refresh(analysis)
            analysis_id = analysis.id

        # Run the pipeline stages with checkpoint support
        await _run_pipeline_stages(project_id, analysis_id, doc_data)

    except Exception as e:
        logger.error(f"Pipeline failed for project {project_id}: {e}", exc_info=True)
        _update_progress(project_id, "failed", 0, 0.0, f"分析失败: {str(e)}")

        # Update project status to failed
        try:
            async with db_module._session_factory() as db:
                result = await db.execute(select(Project).where(Project.id == project_id))
                project = result.scalar_one_or_none()
                if project:
                    project.status = ProjectStatus.FAILED
                    await db.commit()
        except Exception:
            logger.error("Failed to update project status to FAILED", exc_info=True)


async def resume_pipeline(project_id: str, analysis_id: str):
    """Resume a pipeline from the last successful checkpoint."""
    try:
        async with db_module._session_factory() as db:
            result = await db.execute(select(Project).where(Project.id == project_id))
            project = result.scalar_one()
            doc_data = {
                "text": project.doc_text,
                "paragraphs": project.doc_text.split("\n") if project.doc_text else [],
                "headers": [],
                "page_count": project.page_count,
            }

        await _run_pipeline_stages(project_id, analysis_id, doc_data)

    except Exception as e:
        logger.error(f"Pipeline resume failed: {e}", exc_info=True)
        _update_progress(project_id, "failed", 0, 0.0, f"恢复失败: {str(e)}")


async def run_simulation_only(project_id: str, analysis_id: str):
    """Run only simulation + report stages (after persona editing)."""
    try:
        async with db_module._session_factory() as db:
            result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
            analysis = result.scalar_one()
            graph_data = analysis.graph
            personas_data = analysis.personas

        if not graph_data or not personas_data:
            raise ValueError("Graph or personas data not available")

        # Run simulation
        await _run_stage_simulation(project_id, analysis_id, graph_data, personas_data)

        # Run report
        async with db_module._session_factory() as db:
            result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
            analysis = result.scalar_one()
            simulations_data = analysis.simulations

        await _run_stage_report(project_id, analysis_id, graph_data, personas_data, simulations_data)

        # Complete
        async with db_module._session_factory() as db:
            result = await db.execute(select(Project).where(Project.id == project_id))
            project = result.scalar_one()
            project.status = ProjectStatus.COMPLETED
            await db.commit()

            result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
            analysis = result.scalar_one()
            analysis.status = "completed"
            await db.commit()

        _update_progress(project_id, "completed", 4, 1.0, "分析完成！")

    except Exception as e:
        logger.error(f"Simulation-only pipeline failed: {e}", exc_info=True)
        _update_progress(project_id, "failed", 0, 0.0, f"分析失败: {str(e)}")


async def _run_pipeline_stages(project_id: str, analysis_id: str, doc_data: dict):
    """Run all pipeline stages with checkpoint checking."""
    paragraphs = doc_data["paragraphs"]

    # Load checkpoints to determine where to resume
    async with db_module._session_factory() as db:
        checkpoints = await load_checkpoints(db, analysis_id)

    resume_stage = get_resume_stage(checkpoints)
    if resume_stage is None:
        logger.info(f"All stages completed for analysis {analysis_id}")
        return

    logger.info(f"Pipeline starting/resuming from stage: {resume_stage}")

    # ========== Stage 1: Chain 1 - Structure Sensing ==========
    if resume_stage in ("chain1_skeleton", "chain2_fragments", "chain25_graph",
                        "chain3_personas", "chain4_simulations", "chain5_report"):
        if checkpoints.chain1_skeleton.status != "completed":
            _update_progress(project_id, "parsing", 0, 0.5, "正在进行结构感知分析...")

            skeleton_data = await _run_chain1(doc_data, project_id)

            async with db_module._session_factory() as db:
                result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
                analysis = result.scalar_one()
                analysis.skeleton = skeleton_data
                await db.commit()
                await save_stage_output(db, analysis_id, "skeleton", skeleton_data)
                await save_checkpoint(db, analysis_id, "chain1_skeleton", "completed")

            _update_progress(project_id, "parsing", 0, 1.0,
                             f"结构感知完成，识别出 {len(skeleton_data['blocks'])} 个信息块",
                             preview={"block_count": len(skeleton_data["blocks"])})
        else:
            async with db_module._session_factory() as db:
                skeleton_data = await load_stage_output(db, analysis_id, "skeleton")
                if not skeleton_data:
                    result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
                    skeleton_data = result.scalar_one().skeleton

    # ========== Stage 2: Graph Building (Chain 2 + 2.5) ==========
    if checkpoints.chain25_graph.status != "completed":
        async with db_module._session_factory() as db:
            result = await db.execute(select(Project).where(Project.id == project_id))
            project = result.scalar_one()
            project.status = ProjectStatus.GRAPH_BUILDING
            await db.commit()

        def graph_progress(progress, message, preview=None):
            _update_progress(project_id, "graph_building", 1, progress, message, preview)

        _update_progress(project_id, "graph_building", 1, 0.0, "正在构建知识图谱...")

        full_graph_data = await build_graph(
            skeleton=skeleton_data,
            doc_text=doc_data["text"],
            paragraphs=paragraphs,
            progress_callback=graph_progress,
        )

        async with db_module._session_factory() as db:
            result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
            analysis = result.scalar_one()
            analysis.graph = full_graph_data
            await db.commit()
            await save_stage_output(db, analysis_id, "graph", full_graph_data)
            await save_checkpoint(db, analysis_id, "chain25_graph", "completed")
    else:
        async with db_module._session_factory() as db:
            full_graph_data = await load_stage_output(db, analysis_id, "graph")
            if not full_graph_data:
                result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
                full_graph_data = result.scalar_one().graph

    node_count = len(full_graph_data.get("nodes", []))
    edge_count = len(full_graph_data.get("edges", []))

    # ========== Stage 3: Persona Generation (Chain 3) ==========
    if checkpoints.chain3_personas.status != "completed":
        async with db_module._session_factory() as db:
            result = await db.execute(select(Project).where(Project.id == project_id))
            project = result.scalar_one()
            project.status = ProjectStatus.PERSONA_GENERATING
            await db.commit()

        def persona_progress(progress, message, preview=None):
            _update_progress(project_id, "persona_generating", 2, progress, message, preview)

        _update_progress(project_id, "persona_generating", 2, 0.0, "正在生成虚拟用户画像...")

        personas_data = await generate_personas(
            graph=full_graph_data,
            progress_callback=persona_progress,
        )

        async with db_module._session_factory() as db:
            result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
            analysis = result.scalar_one()
            analysis.personas = personas_data
            await db.commit()
            await save_stage_output(db, analysis_id, "personas", personas_data)
            await save_checkpoint(db, analysis_id, "chain3_personas", "completed")
    else:
        async with db_module._session_factory() as db:
            personas_data = await load_stage_output(db, analysis_id, "personas")
            if not personas_data:
                result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
                personas_data = result.scalar_one().personas

    persona_count = len(personas_data.get("personas", []))

    # ========== Stage 4: Simulation (Chain 4) ==========
    await _run_stage_simulation(project_id, analysis_id, full_graph_data, personas_data)

    async with db_module._session_factory() as db:
        result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
        simulations_data = result.scalar_one().simulations

    sim_count = len(simulations_data) if simulations_data else 0

    # ========== Stage 5: Report (Chain 5) ==========
    await _run_stage_report(project_id, analysis_id, full_graph_data, personas_data, simulations_data)

    # ========== Pipeline Complete ==========
    async with db_module._session_factory() as db:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one()
        project.status = ProjectStatus.COMPLETED
        await db.commit()

        result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
        analysis = result.scalar_one()
        analysis.status = "completed"
        await db.commit()

    async with db_module._session_factory() as db:
        result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
        analysis = result.scalar_one()
        report_data = analysis.report or {}

    _update_progress(project_id, "completed", 4, 1.0, "分析完成！",
                     preview={
                         "nodes": node_count,
                         "personas": persona_count,
                         "simulations": sim_count,
                         "blind_spots": len(report_data.get("blind_spots", [])),
                         "bottlenecks": len(report_data.get("bottlenecks", [])),
                     })

    logger.info(f"Full pipeline completed for project {project_id}")


async def _run_stage_simulation(
    project_id: str,
    analysis_id: str,
    graph_data: dict,
    personas_data: dict,
):
    """Run simulation stage with checkpoint."""
    async with db_module._session_factory() as db:
        checkpoints = await load_checkpoints(db, analysis_id)

    if checkpoints.chain4_simulations.status == "completed":
        return

    async with db_module._session_factory() as db:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one()
        project.status = ProjectStatus.SIMULATING
        await db.commit()

    def simulation_progress(progress, message, preview=None):
        _update_progress(project_id, "simulating", 3, progress, message, preview)

    _update_progress(project_id, "simulating", 3, 0.0, "正在进行多场景叙事仿真...")

    simulations_data = await run_simulation(
        graph=graph_data,
        personas=personas_data,
        analysis_id=analysis_id,
        progress_callback=simulation_progress,
    )

    async with db_module._session_factory() as db:
        result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
        analysis = result.scalar_one()
        analysis.simulations = simulations_data
        await db.commit()
        await save_stage_output(db, analysis_id, "simulations", simulations_data)
        await save_checkpoint(db, analysis_id, "chain4_simulations", "completed")


async def _run_stage_report(
    project_id: str,
    analysis_id: str,
    graph_data: dict,
    personas_data: dict,
    simulations_data: list,
):
    """Run report stage with checkpoint."""
    async with db_module._session_factory() as db:
        checkpoints = await load_checkpoints(db, analysis_id)

    if checkpoints.chain5_report.status == "completed":
        return

    async with db_module._session_factory() as db:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one()
        project.status = ProjectStatus.REPORTING
        await db.commit()

    def report_progress(progress, message, preview=None):
        _update_progress(project_id, "reporting", 4, progress, message, preview)

    _update_progress(project_id, "reporting", 4, 0.0, "正在生成压测报告...")

    report_data = await generate_report(
        graph=graph_data,
        personas=personas_data,
        simulations=simulations_data,
        analysis_id=analysis_id,
        progress_callback=report_progress,
    )

    async with db_module._session_factory() as db:
        result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
        analysis = result.scalar_one()
        analysis.report = report_data
        await db.commit()
        await save_stage_output(db, analysis_id, "report", report_data)
        await save_checkpoint(db, analysis_id, "chain5_report", "completed")


async def _run_chain1(doc_data: dict, project_id: str) -> dict:
    """Run Chain 1: Structure Sensing with validation and retry logic."""
    paragraphs = doc_data["paragraphs"]
    full_text = doc_data["text"]
    total_chars = sum(len(p) for p in paragraphs)

    # Choose prompt based on document length
    if total_chars > LONG_DOC_THRESHOLD:
        summary = extract_headers_summary(paragraphs, doc_data["headers"])
        user_prompt = CHAIN1_USER_PROMPT_LONG.format(
            total_paragraphs=len(paragraphs),
            summary_text=summary,
        )
    else:
        user_prompt = CHAIN1_USER_PROMPT.format(doc_text=full_text)

    # First attempt
    result = await llm_call(
        prompt=user_prompt,
        system_prompt=CHAIN1_SYSTEM_PROMPT,
        output_format="json",
        temperature=0.3,
    )

    # Validate and retry if needed
    for attempt in range(MAX_RETRIES):
        errors = _validate_chain1_output(result)
        if not errors:
            break

        logger.warning(f"Chain 1 validation failed (attempt {attempt + 1}): {errors}")
        _update_progress(
            project_id, "parsing", 0, 0.6 + attempt * 0.1,
            f"校验失败，正在重试 ({attempt + 1}/{MAX_RETRIES})...",
        )

        retry_prompt = CHAIN1_RETRY_PROMPT.format(
            errors="\n".join(f"- {e}" for e in errors),
            doc_text=full_text if total_chars <= LONG_DOC_THRESHOLD else extract_headers_summary(paragraphs, doc_data["headers"]),
        )
        result = await llm_call(
            prompt=retry_prompt,
            system_prompt=CHAIN1_SYSTEM_PROMPT,
            output_format="json",
            temperature=0.2,
        )

    # Final validation
    final_errors = _validate_chain1_output(result)
    if final_errors:
        logger.error(f"Chain 1 still has errors after retries: {final_errors}")

    skeleton = DocumentSkeleton(**result)
    return skeleton.model_dump()


def _validate_chain1_output(data: dict) -> list[str]:
    """Validate Chain 1 output structure."""
    errors = []

    if "blocks" not in data:
        errors.append("缺少 'blocks' 字段")
        return errors

    blocks = data["blocks"]
    if not isinstance(blocks, list) or len(blocks) == 0:
        errors.append("'blocks' 必须是非空数组")
        return errors

    errors.extend(validate_block_ids(blocks))
    errors.extend(validate_source_ranges(blocks))

    valid_types = {
        "product_overview", "user_story", "feature_spec",
        "data_model", "non_functional", "business_rule", "ui_flow",
    }
    for block in blocks:
        if block.get("type") not in valid_types:
            errors.append(f"无效的 block type: {block.get('type')} (block_id: {block.get('block_id')})")
        sr = block.get("source_range", [])
        if not isinstance(sr, list) or len(sr) != 2:
            errors.append(f"source_range 格式错误 (block_id: {block.get('block_id')})")
        elif sr[0] > sr[1]:
            errors.append(f"source_range start > end (block_id: {block.get('block_id')})")

    return errors


def _update_progress(
    project_id: str,
    stage: str,
    stage_index: int,
    progress: float,
    message: str,
    preview: dict | None = None,
):
    """Update in-memory progress for a project."""
    _progress[project_id] = {
        "stage": stage,
        "stage_index": stage_index,
        "progress": progress,
        "message": message,
        "preview": preview,
    }
