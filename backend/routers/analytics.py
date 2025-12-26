from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from datetime import datetime, timedelta
from typing import Dict, List

from ..database import get_db
from ..models import Project, Task, User, Organization
from ..routers.auth import oauth2_scheme, get_current_user

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

@router.get("/dashboard/overview")
async def get_dashboard_overview(
    organization_id: int = Query(...),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> Dict:
    """Get dashboard overview metrics"""
    current_user = await get_current_user(token, db)
    
    # Get project stats
    projects_result = await db.execute(
        select(func.count(Project.id)).where(
            Project.organization_id == organization_id
        )
    )
    total_projects = projects_result.scalar() or 0
    
    # Get active projects
    active_projects_result = await db.execute(
        select(func.count(Project.id)).where(
            (Project.organization_id == organization_id) &
            (Project.status == 'active')
        )
    )
    active_projects = active_projects_result.scalar() or 0
    
    # Get tasks stats
    tasks_result = await db.execute(
        select(func.count(Task.id)).where(
            Task.project_id.in_(
                select(Project.id).where(Project.organization_id == organization_id)
            )
        )
    )
    total_tasks = tasks_result.scalar() or 0
    
    # Get completed tasks
    completed_tasks_result = await db.execute(
        select(func.count(Task.id)).where(
            (Task.project_id.in_(
                select(Project.id).where(Project.organization_id == organization_id)
            )) &
            (Task.status == 'completed')
        )
    )
    completed_tasks = completed_tasks_result.scalar() or 0
    
    # Get team members
    org_result = await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    org = org_result.scalar_one_or_none()
    team_size = len(org.members) if org else 0
    
    return {
        "total_projects": total_projects,
        "active_projects": active_projects,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "completion_rate": (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0,
        "team_size": team_size
    }

@router.get("/projects/status-breakdown")
async def get_project_status_breakdown(
    organization_id: int = Query(...),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> List[Dict]:
    """Get project status breakdown"""
    await get_current_user(token, db)
    
    result = await db.execute(
        select(
            Project.status,
            func.count(Project.id).label('count')
        ).where(
            Project.organization_id == organization_id
        ).group_by(Project.status)
    )
    
    data = []
    for row in result.all():
        data.append({
            "status": row[0],
            "count": row[1]
        })
    
    return data

@router.get("/tasks/priority-distribution")
async def get_task_priority_distribution(
    organization_id: int = Query(...),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> List[Dict]:
    """Get task priority distribution"""
    await get_current_user(token, db)
    
    result = await db.execute(
        select(
            Task.priority,
            func.count(Task.id).label('count')
        ).where(
            Task.project_id.in_(
                select(Project.id).where(Project.organization_id == organization_id)
            )
        ).group_by(Task.priority)
    )
    
    data = []
    for row in result.all():
        data.append({
            "priority": row[0],
            "count": row[1]
        })
    
    return data

@router.get("/tasks/status-trend")
async def get_task_status_trend(
    organization_id: int = Query(...),
    days: int = Query(30, ge=1, le=365),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> List[Dict]:
    """Get task completion trend over time"""
    await get_current_user(token, db)
    
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    result = await db.execute(
        select(
            func.date(Task.completed_at).label('date'),
            func.count(Task.id).label('completed')
        ).where(
            (Task.project_id.in_(
                select(Project.id).where(Project.organization_id == organization_id)
            )) &
            (Task.completed_at >= cutoff_date) &
            (Task.status == 'completed')
        ).group_by(func.date(Task.completed_at)).order_by('date')
    )
    
    data = []
    for row in result.all():
        data.append({
            "date": str(row[0]) if row[0] else None,
            "completed_count": row[1]
        })
    
    return data

@router.get("/team/workload")
async def get_team_workload(
    organization_id: int = Query(...),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> List[Dict]:
    """Get team member workload"""
    await get_current_user(token, db)
    
    result = await db.execute(
        select(
            User.username,
            func.count(Task.id).label('task_count')
        ).outerjoin(
            Task, Task.assigned_to == User.id
        ).where(
            User.id.in_(
                select(Organization.members).where(Organization.id == organization_id)
            )
        ).group_by(User.id, User.username)
    )
    
    data = []
    for row in result.all():
        data.append({
            "user": row[0],
            "assigned_tasks": row[1]
        })
    
    return data