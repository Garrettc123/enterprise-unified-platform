from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, desc
from typing import List
import asyncio

from ..database import get_db
from ..models import Project, Task, User, Organization
from ..schemas import ProjectResponse, TaskResponse, UserResponse
from ..routers.auth import oauth2_scheme, get_current_user

router = APIRouter(prefix="/api/search", tags=["search"])

class SearchResult:
    def __init__(self, type_: str, id: int, title: str, description: str, relevance: float):
        self.type = type_
        self.id = id
        self.title = title
        self.description = description
        self.relevance = relevance

@router.get("/")
async def global_search(
    q: str = Query(..., min_length=2),
    type_filter: str = Query(None),
    organization_id: int = Query(...),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> List[dict]:
    """Global search across projects, tasks, and users - optimized with parallel queries"""
    await get_current_user(token, db)

    results = []

    # Optimized: Run all queries in parallel using asyncio.gather
    async def search_projects():
        if not type_filter or type_filter == "project":
            projects_result = await db.execute(
                select(Project).where(
                    (Project.organization_id == organization_id) &
                    (or_(
                        Project.name.ilike(f"%{q}%"),
                        Project.description.ilike(f"%{q}%")
                    ))
                ).limit(limit)
            )
            return [
                {
                    "type": "project",
                    "id": project.id,
                    "title": project.name,
                    "description": project.description,
                    "url": f"/projects/{project.id}"
                }
                for project in projects_result.scalars()
            ]
        return []

    async def search_tasks():
        if not type_filter or type_filter == "task":
            tasks_result = await db.execute(
                select(Task).where(
                    (Task.project_id.in_(
                        select(Project.id).where(Project.organization_id == organization_id)
                    )) &
                    (or_(
                        Task.title.ilike(f"%{q}%"),
                        Task.description.ilike(f"%{q}%")
                    ))
                ).limit(limit)
            )
            return [
                {
                    "type": "task",
                    "id": task.id,
                    "title": task.title,
                    "description": task.description,
                    "url": f"/tasks/{task.id}"
                }
                for task in tasks_result.scalars()
            ]
        return []

    async def search_users():
        if not type_filter or type_filter == "user":
            users_result = await db.execute(
                select(User).where(
                    or_(
                        User.username.ilike(f"%{q}%"),
                        User.full_name.ilike(f"%{q}%"),
                        User.email.ilike(f"%{q}%")
                    )
                ).limit(limit)
            )
            return [
                {
                    "type": "user",
                    "id": user.id,
                    "title": user.full_name or user.username,
                    "description": user.email,
                    "url": f"/users/{user.id}"
                }
                for user in users_result.scalars()
            ]
        return []

    # Execute all searches in parallel
    project_results, task_results, user_results = await asyncio.gather(
        search_projects(),
        search_tasks(),
        search_users()
    )

    # Combine results
    results = project_results + task_results + user_results

    return results[skip:skip+limit]

@router.get("/projects")
async def search_projects(
    q: str = Query(..., min_length=2),
    organization_id: int = Query(...),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Search projects"""
    await get_current_user(token, db)
    
    result = await db.execute(
        select(Project).where(
            (Project.organization_id == organization_id) &
            (or_(
                Project.name.ilike(f"%{q}%"),
                Project.description.ilike(f"%{q}%")
            ))
        ).order_by(desc(Project.created_at)).offset(skip).limit(limit)
    )
    
    return result.scalars().all()

@router.get("/tasks")
async def search_tasks(
    q: str = Query(..., min_length=2),
    organization_id: int = Query(...),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Search tasks"""
    await get_current_user(token, db)
    
    result = await db.execute(
        select(Task).where(
            (Task.project_id.in_(
                select(Project.id).where(Project.organization_id == organization_id)
            )) &
            (or_(
                Task.title.ilike(f"%{q}%"),
                Task.description.ilike(f"%{q}%")
            ))
        ).order_by(desc(Task.created_at)).offset(skip).limit(limit)
    )
    
    return result.scalars().all()