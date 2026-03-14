"""Checkpoint service - manages pipeline stage persistence and recovery."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Analysis, StageOutput
from app.models.schema import AnalysisCheckpoints, CheckpointState

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def load_checkpoints(db: AsyncSession, analysis_id: str) -> AnalysisCheckpoints:
    """Load checkpoint state for an analysis."""
    result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
    analysis = result.scalar_one_or_none()
    if not analysis or not analysis.checkpoints:
        return AnalysisCheckpoints()
    return AnalysisCheckpoints(**analysis.checkpoints)


async def save_checkpoint(
    db: AsyncSession,
    analysis_id: str,
    stage: str,
    status: str,
    error: str | None = None,
):
    """Update checkpoint state for a specific stage."""
    result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
    analysis = result.scalar_one()

    checkpoints = AnalysisCheckpoints(**(analysis.checkpoints or {}))
    state = CheckpointState(
        status=status,
        timestamp=_now_iso(),
        error=error,
    )

    # Update the specific stage checkpoint
    setattr(checkpoints, stage, state)
    analysis.checkpoints = checkpoints.model_dump()
    await db.commit()


async def save_stage_output(
    db: AsyncSession,
    analysis_id: str,
    stage: str,
    data: dict,
):
    """Save a chain's output independently to stage_outputs table."""
    # Check if a stage output already exists for this analysis+stage
    result = await db.execute(
        select(StageOutput).where(
            StageOutput.analysis_id == analysis_id,
            StageOutput.stage == stage,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.data = data
    else:
        output = StageOutput(
            analysis_id=analysis_id,
            stage=stage,
            data=data,
        )
        db.add(output)

    await db.commit()


async def load_stage_output(
    db: AsyncSession,
    analysis_id: str,
    stage: str,
) -> dict | None:
    """Load a chain's output from stage_outputs table."""
    result = await db.execute(
        select(StageOutput).where(
            StageOutput.analysis_id == analysis_id,
            StageOutput.stage == stage,
        )
    )
    output = result.scalar_one_or_none()
    return output.data if output else None


def get_resume_stage(checkpoints: AnalysisCheckpoints) -> str | None:
    """Determine which stage to resume from based on checkpoint state.

    Returns the name of the first incomplete stage, or None if all completed.
    """
    stages = [
        "chain1_skeleton",
        "chain2_fragments",
        "chain25_graph",
        "chain3_personas",
        "chain4_simulations",
        "chain5_report",
    ]

    for stage in stages:
        state: CheckpointState = getattr(checkpoints, stage)
        if state.status != "completed":
            return stage

    return None  # All stages completed
