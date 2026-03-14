"""WebSocket endpoints for real-time updates.

v2.0: Added action log streaming during simulation.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select, func

from app.services.pipeline import get_progress
from app.models import database as db_module
from app.models.database import ActionLog, Analysis

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws/progress/{project_id}")
async def ws_progress(websocket: WebSocket, project_id: str):
    """Push pipeline progress to the frontend via WebSocket.

    Polls the in-memory progress store every 1s and sends updates
    when the data changes.
    """
    await websocket.accept()
    last_sent = None

    try:
        while True:
            progress = get_progress(project_id)
            if progress and progress != last_sent:
                await websocket.send_text(json.dumps(progress, ensure_ascii=False))
                last_sent = dict(progress)

                if progress.get("stage") in ("completed", "failed"):
                    await asyncio.sleep(0.5)
                    break

            await asyncio.sleep(1)
    except WebSocketDisconnect:
        logger.debug(f"WebSocket disconnected for project {project_id}")
    except Exception as e:
        logger.warning(f"WebSocket error for project {project_id}: {e}")


@router.websocket("/ws/simulation/{project_id}")
async def ws_simulation_stream(websocket: WebSocket, project_id: str):
    """Stream action logs in real-time during simulation.

    v2.0: Polls the action_logs table for new entries and pushes them
    to the frontend for live simulation visualization.
    """
    await websocket.accept()
    last_log_id = 0

    try:
        # Get the latest analysis for this project
        async with db_module._session_factory() as db:
            result = await db.execute(
                select(Analysis)
                .where(Analysis.project_id == project_id)
                .order_by(Analysis.version.desc())
            )
            analysis = result.scalar_one_or_none()
            if not analysis:
                await websocket.send_text(json.dumps({"error": "Analysis not found"}))
                return
            analysis_id = analysis.id

        while True:
            # Check if simulation is still running
            progress = get_progress(project_id)
            stage = progress.get("stage", "") if progress else ""

            # Fetch new action logs since last check
            try:
                async with db_module._session_factory() as db:
                    result = await db.execute(
                        select(ActionLog)
                        .where(
                            ActionLog.analysis_id == analysis_id,
                            ActionLog.id > last_log_id,
                        )
                        .order_by(ActionLog.id)
                        .limit(20)
                    )
                    new_logs = result.scalars().all()

                    if new_logs:
                        logs_data = []
                        for log in new_logs:
                            logs_data.append({
                                "id": log.id,
                                "persona_id": log.persona_id,
                                "step": log.step,
                                "scene": log.scene,
                                "action": log.action,
                                "target": log.target,
                                "emotion": log.emotion,
                                "thought": log.thought,
                                "friction": log.friction,
                            })
                            last_log_id = log.id

                        await websocket.send_text(json.dumps({
                            "type": "action_logs",
                            "logs": logs_data,
                        }, ensure_ascii=False))
            except Exception as e:
                logger.warning(f"Error fetching action logs: {e}")

            # Stop streaming when simulation is done
            if stage in ("reporting", "completed", "failed"):
                await websocket.send_text(json.dumps({
                    "type": "simulation_complete",
                    "stage": stage,
                }))
                await asyncio.sleep(1)
                break

            await asyncio.sleep(1.5)

    except WebSocketDisconnect:
        logger.debug(f"Simulation WS disconnected for project {project_id}")
    except Exception as e:
        logger.warning(f"Simulation WS error: {e}")
