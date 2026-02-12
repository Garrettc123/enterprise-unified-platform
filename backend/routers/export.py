from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import csv
import json
from io import StringIO, BytesIO
from datetime import datetime

from ..database import get_db
from ..models import Project, Task, User, Organization
from ..routers.auth import oauth2_scheme, get_current_user

router = APIRouter(prefix="/api/export", tags=["export"])

@router.get(
    "/projects/csv",
    summary="Export projects as CSV",
)
async def export_projects_csv(
    organization_id: int = Query(..., description="Organization ID"),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Download all projects in an organization as a CSV file."""
    await get_current_user(token, db)
    
    result = await db.execute(
        select(Project).where(Project.organization_id == organization_id)
    )
    projects = result.scalars().all()
    
    # Create CSV
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Name', 'Status', 'Priority', 'Budget', 'Created At'])
    
    for project in projects:
        writer.writerow([
            project.id,
            project.name,
            project.status,
            project.priority,
            project.budget,
            project.created_at.isoformat()
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=projects.csv"}
    )

@router.get(
    "/tasks/csv",
    summary="Export tasks as CSV",
)
async def export_tasks_csv(
    project_id: int = Query(..., description="Project ID"),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Download all tasks in a project as a CSV file."""
    await get_current_user(token, db)
    
    result = await db.execute(
        select(Task).where(Task.project_id == project_id)
    )
    tasks = result.scalars().all()
    
    # Create CSV
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Title', 'Status', 'Priority', 'Assigned To', 'Due Date', 'Created At'])
    
    for task in tasks:
        writer.writerow([
            task.id,
            task.title,
            task.status,
            task.priority,
            task.assigned_to,
            task.due_date.isoformat() if task.due_date else '',
            task.created_at.isoformat()
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=tasks.csv"}
    )

@router.get(
    "/projects/json",
    summary="Export projects as JSON",
)
async def export_projects_json(
    organization_id: int = Query(..., description="Organization ID"),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Download all projects in an organization as a JSON file."""
    await get_current_user(token, db)
    
    result = await db.execute(
        select(Project).where(Project.organization_id == organization_id)
    )
    projects = result.scalars().all()
    
    data = []
    for project in projects:
        data.append({
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "status": project.status,
            "priority": project.priority,
            "budget": project.budget,
            "created_at": project.created_at.isoformat()
        })
    
    output = json.dumps(data, indent=2)
    return StreamingResponse(
        iter([output]),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=projects.json"}
    )

@router.get(
    "/tasks/json",
    summary="Export tasks as JSON",
)
async def export_tasks_json(
    project_id: int = Query(..., description="Project ID"),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Download all tasks in a project as a JSON file."""
    await get_current_user(token, db)
    
    result = await db.execute(
        select(Task).where(Task.project_id == project_id)
    )
    tasks = result.scalars().all()
    
    data = []
    for task in tasks:
        data.append({
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "status": task.status,
            "priority": task.priority,
            "assigned_to": task.assigned_to,
            "due_date": task.due_date.isoformat() if task.due_date else None,
            "created_at": task.created_at.isoformat()
        })
    
    output = json.dumps(data, indent=2)
    return StreamingResponse(
        iter([output]),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=tasks.json"}
    )