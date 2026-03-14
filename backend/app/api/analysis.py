"""Analysis results API endpoints - v2.0 with action logs, persona editing, and retry."""

import asyncio
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db, Project, Analysis, ActionLog
from app.models.schema import (
    ProgressResponse,
    PersonaUpdateRequest,
    CustomPersonaRequest,
    Persona,
)
from app.services.pipeline import get_progress, resume_pipeline, run_simulation_only

router = APIRouter(tags=["analysis"])


@router.get("/projects/{project_id}")
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    """Get project status and basic info."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(404, "Project not found")
    return {
        "id": project.id,
        "name": project.name,
        "status": project.status,
        "filename": project.filename,
        "context": project.context,
        "created_at": project.created_at,
    }


@router.get("/progress/{project_id}", response_model=ProgressResponse)
async def get_pipeline_progress(project_id: str):
    """Get real-time pipeline progress for a project."""
    progress = get_progress(project_id)
    if not progress:
        return ProgressResponse(stage="unknown", stage_index=0, progress=0.0, message="暂无进度信息")
    return ProgressResponse(**progress)


@router.get("/analysis/{project_id}")
async def get_analysis(project_id: str, db: AsyncSession = Depends(get_db)):
    """Get the latest analysis results for a project."""
    result = await db.execute(
        select(Analysis)
        .where(Analysis.project_id == project_id)
        .order_by(Analysis.version.desc())
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(404, "Analysis not found")
    return {
        "id": analysis.id,
        "project_id": analysis.project_id,
        "version": analysis.version,
        "status": analysis.status,
        "skeleton": analysis.skeleton,
        "graph": analysis.graph,
        "personas": analysis.personas,
        "simulations": analysis.simulations,
        "report": analysis.report,
        "checkpoints": analysis.checkpoints,
    }


@router.get("/analysis/{project_id}/personas")
async def get_personas(project_id: str, db: AsyncSession = Depends(get_db)):
    """Get generated personas for a project."""
    result = await db.execute(
        select(Analysis)
        .where(Analysis.project_id == project_id)
        .order_by(Analysis.version.desc())
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(404, "Analysis not found")
    if not analysis.personas:
        raise HTTPException(404, "Personas not yet generated")
    return analysis.personas


@router.get("/analysis/{project_id}/simulations")
async def get_simulations(project_id: str, db: AsyncSession = Depends(get_db)):
    """Get simulation results for a project."""
    result = await db.execute(
        select(Analysis)
        .where(Analysis.project_id == project_id)
        .order_by(Analysis.version.desc())
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(404, "Analysis not found")
    if not analysis.simulations:
        raise HTTPException(404, "Simulations not yet completed")
    return analysis.simulations


@router.get("/analysis/{project_id}/report")
async def get_report(project_id: str, db: AsyncSession = Depends(get_db)):
    """Get the stress test report for a project."""
    result = await db.execute(
        select(Analysis)
        .where(Analysis.project_id == project_id)
        .order_by(Analysis.version.desc())
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(404, "Analysis not found")
    if not analysis.report:
        raise HTTPException(404, "Report not yet generated")
    return analysis.report


# --- v2.0 New Endpoints ---


@router.get("/analysis/{project_id}/action-logs")
async def get_action_logs(
    project_id: str,
    persona_id: str | None = Query(None),
    scene: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get structured action logs for an analysis, with optional filters."""
    # Get the latest analysis
    result = await db.execute(
        select(Analysis)
        .where(Analysis.project_id == project_id)
        .order_by(Analysis.version.desc())
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(404, "Analysis not found")

    # Query action logs
    query = select(ActionLog).where(ActionLog.analysis_id == analysis.id)
    if persona_id:
        query = query.where(ActionLog.persona_id == persona_id)
    if scene:
        query = query.where(ActionLog.scene == scene)
    query = query.order_by(ActionLog.persona_id, ActionLog.step)

    result = await db.execute(query)
    logs = result.scalars().all()

    return [
        {
            "id": log.id,
            "persona_id": log.persona_id,
            "step": log.step,
            "scene": log.scene,
            "action": log.action,
            "target": log.target,
            "emotion": log.emotion,
            "thought": log.thought,
            "friction": log.friction,
        }
        for log in logs
    ]


@router.post("/analysis/{project_id}/retry")
async def retry_analysis(
    project_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Resume analysis from the last successful checkpoint."""
    result = await db.execute(
        select(Analysis)
        .where(Analysis.project_id == project_id)
        .order_by(Analysis.version.desc())
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(404, "Analysis not found")

    if analysis.status == "running":
        raise HTTPException(409, "Analysis is already running")

    # Update status
    analysis.status = "running"
    await db.commit()

    # Resume in background
    background_tasks.add_task(resume_pipeline, project_id, analysis.id)

    return {"message": "Pipeline resuming from last checkpoint", "analysis_id": analysis.id}


@router.put("/analysis/{project_id}/personas")
async def update_personas(
    project_id: str,
    request: PersonaUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update personas (user editing before simulation)."""
    result = await db.execute(
        select(Analysis)
        .where(Analysis.project_id == project_id)
        .order_by(Analysis.version.desc())
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(404, "Analysis not found")

    # Validate and save
    personas_data = {"personas": [p.model_dump() for p in request.personas]}
    analysis.personas = personas_data
    await db.commit()

    return {"message": "Personas updated", "count": len(request.personas)}


@router.post("/analysis/{project_id}/personas/custom")
async def generate_custom_persona(
    project_id: str,
    request: CustomPersonaRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate a structured persona from natural language description."""
    from app.services.persona_gen import generate_custom_persona as gen_custom

    result = await db.execute(
        select(Analysis)
        .where(Analysis.project_id == project_id)
        .order_by(Analysis.version.desc())
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(404, "Analysis not found")

    # Generate persona from description
    persona = await gen_custom(request.description, analysis.personas)
    return persona


@router.post("/analysis/{project_id}/simulate")
async def trigger_simulation(
    project_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger simulation with current personas (after user editing/confirmation)."""
    result = await db.execute(
        select(Analysis)
        .where(Analysis.project_id == project_id)
        .order_by(Analysis.version.desc())
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(404, "Analysis not found")

    if not analysis.personas:
        raise HTTPException(400, "No personas available for simulation")
    if not analysis.graph:
        raise HTTPException(400, "Graph not available")

    # Reset simulation and report checkpoints
    checkpoints = analysis.checkpoints or {}
    checkpoints["chain4_simulations"] = {"status": "pending"}
    checkpoints["chain5_report"] = {"status": "pending"}
    analysis.checkpoints = checkpoints
    analysis.simulations = None
    analysis.report = None
    analysis.status = "running"
    await db.commit()

    # Run simulation + report in background
    background_tasks.add_task(run_simulation_only, project_id, analysis.id)

    return {"message": "Simulation started", "analysis_id": analysis.id}
