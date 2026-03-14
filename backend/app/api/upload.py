"""File upload and project management API endpoints.

v2.0: Added project listing, context support.
"""

import asyncio
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.database import get_db, Project, Analysis
from app.models.schema import UploadResponse
from app.services.pipeline import run_parsing_pipeline

router = APIRouter(tags=["upload"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".md"}


@router.get("/projects")
async def list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List all projects, newest first."""
    result = await db.execute(
        select(Project)
        .order_by(Project.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    projects = result.scalars().all()

    items = []
    for p in projects:
        # Get latest analysis status
        analysis_result = await db.execute(
            select(Analysis.status)
            .where(Analysis.project_id == p.id)
            .order_by(Analysis.version.desc())
            .limit(1)
        )
        analysis_status = analysis_result.scalar_one_or_none()

        items.append({
            "id": p.id,
            "name": p.name,
            "filename": p.filename,
            "status": analysis_status or p.status,
            "context": p.context,
            "created_at": p.created_at,
        })

    # Total count
    count_result = await db.execute(select(func.count(Project.id)))
    total = count_result.scalar() or 0

    return {"items": items, "total": total}


@router.post("/upload", response_model=UploadResponse)
async def upload_prd(
    file: UploadFile = File(...),
    context: str = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """Upload a PRD document (PDF/DOCX/MD) for analysis.

    v2.0: Accepts optional context JSON string with background info.
    """
    settings = get_settings()

    # Validate file extension
    filename = file.filename or ""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: {ext}. Allowed: {ALLOWED_EXTENSIONS}")

    # Validate file size
    content = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(400, f"File too large. Max: {settings.max_upload_size_mb}MB")

    # Parse context if provided
    context_data = None
    if context:
        import json
        try:
            context_data = json.loads(context)
        except json.JSONDecodeError:
            raise HTTPException(400, "Invalid context JSON")

    # Create project
    project = Project(
        name=filename.rsplit(".", 1)[0],
        filename=filename,
        context=context_data,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    # Trigger async parsing pipeline in background
    asyncio.create_task(run_parsing_pipeline(project.id, content, filename))

    return UploadResponse(
        project_id=project.id,
        filename=filename,
        pages=0,
        estimated_time=15,
    )
