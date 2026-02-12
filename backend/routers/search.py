from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, desc, func
from typing import List, Optional

from ..database import get_db
from ..models import Project, Task, User, Organization
from ..schemas import (
    ProjectResponse,
    TaskResponse,
    UserResponse,
    SearchResponse,
    SearchResultItem,
    SearchSuggestion,
    ReindexResponse,
)
from ..routers.auth import oauth2_scheme, get_current_user
from ..elasticsearch_service import get_elasticsearch_service

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("/", response_model=SearchResponse)
async def global_search(
    q: str = Query(..., min_length=2),
    type_filter: Optional[str] = Query(None),
    organization_id: int = Query(...),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """Global search across projects, tasks, and users.

    Uses Elasticsearch for full-text search when available,
    with automatic fallback to database ILIKE queries.
    """
    await get_current_user(token, db)

    es = get_elasticsearch_service()

    # Try Elasticsearch first
    if es and es.is_available:
        entity_types = None
        if type_filter:
            type_map = {"project": "projects", "task": "tasks", "user": "users"}
            entity_type = type_map.get(type_filter)
            if entity_type:
                entity_types = [entity_type]

        es_results = await es.search(
            query=q,
            entity_types=entity_types,
            organization_id=organization_id,
            skip=skip,
            limit=limit,
        )

        results = [
            SearchResultItem(
                type=r["type"],
                id=r["id"],
                title=r["title"],
                description=r.get("description"),
                score=r.get("score"),
                url=r["url"],
                highlights=r.get("highlights"),
            )
            for r in es_results["results"]
        ]

        return SearchResponse(
            results=results,
            total=es_results["total"],
            query=q,
            source="elasticsearch",
        )

    # Fallback to database search
    results = []

    if not type_filter or type_filter == "project":
        projects_result = await db.execute(
            select(Project)
            .where(
                (Project.organization_id == organization_id)
                & (
                    or_(
                        Project.name.ilike(f"%{q}%"),
                        Project.description.ilike(f"%{q}%"),
                    )
                )
            )
            .limit(limit)
        )
        for project in projects_result.scalars():
            results.append(
                SearchResultItem(
                    type="project",
                    id=project.id,
                    title=project.name,
                    description=project.description,
                    url=f"/projects/{project.id}",
                )
            )

    if not type_filter or type_filter == "task":
        tasks_result = await db.execute(
            select(Task)
            .where(
                (
                    Task.project_id.in_(
                        select(Project.id).where(
                            Project.organization_id == organization_id
                        )
                    )
                )
                & (
                    or_(
                        Task.title.ilike(f"%{q}%"),
                        Task.description.ilike(f"%{q}%"),
                    )
                )
            )
            .limit(limit)
        )
        for task in tasks_result.scalars():
            results.append(
                SearchResultItem(
                    type="task",
                    id=task.id,
                    title=task.title,
                    description=task.description,
                    url=f"/tasks/{task.id}",
                )
            )

    if not type_filter or type_filter == "user":
        users_result = await db.execute(
            select(User)
            .where(
                or_(
                    User.username.ilike(f"%{q}%"),
                    User.full_name.ilike(f"%{q}%"),
                    User.email.ilike(f"%{q}%"),
                )
            )
            .limit(limit)
        )
        for user in users_result.scalars():
            results.append(
                SearchResultItem(
                    type="user",
                    id=user.id,
                    title=user.full_name or user.username,
                    description=user.email,
                    url=f"/users/{user.id}",
                )
            )

    paginated = results[skip : skip + limit]
    return SearchResponse(
        results=paginated,
        total=len(results),
        query=q,
        source="database",
    )


@router.get("/projects")
async def search_projects(
    q: str = Query(..., min_length=2),
    organization_id: int = Query(...),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Search projects"""
    await get_current_user(token, db)

    result = await db.execute(
        select(Project)
        .where(
            (Project.organization_id == organization_id)
            & (
                or_(
                    Project.name.ilike(f"%{q}%"),
                    Project.description.ilike(f"%{q}%"),
                )
            )
        )
        .order_by(desc(Project.created_at))
        .offset(skip)
        .limit(limit)
    )

    return result.scalars().all()


@router.get("/tasks")
async def search_tasks(
    q: str = Query(..., min_length=2),
    organization_id: int = Query(...),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Search tasks"""
    await get_current_user(token, db)

    result = await db.execute(
        select(Task)
        .where(
            (
                Task.project_id.in_(
                    select(Project.id).where(
                        Project.organization_id == organization_id
                    )
                )
            )
            & (
                or_(
                    Task.title.ilike(f"%{q}%"),
                    Task.description.ilike(f"%{q}%"),
                )
            )
        )
        .order_by(desc(Task.created_at))
        .offset(skip)
        .limit(limit)
    )

    return result.scalars().all()


@router.get("/suggestions", response_model=List[SearchSuggestion])
async def search_suggestions(
    q: str = Query(..., min_length=2),
    limit: int = Query(5, ge=1, le=20),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> List[SearchSuggestion]:
    """Get search suggestions using Elasticsearch prefix matching.

    Falls back to database prefix search when Elasticsearch is unavailable.
    """
    await get_current_user(token, db)

    es = get_elasticsearch_service()

    if es and es.is_available:
        suggestions = await es.suggest(query=q, limit=limit)
        return [
            SearchSuggestion(type=s["type"], id=s["id"], title=s["title"])
            for s in suggestions
        ]

    # Database fallback for suggestions
    suggestions = []

    projects_result = await db.execute(
        select(Project.id, Project.name)
        .where(Project.name.ilike(f"{q}%"))
        .limit(limit)
    )
    for row in projects_result:
        suggestions.append(
            SearchSuggestion(type="project", id=row.id, title=row.name)
        )

    tasks_result = await db.execute(
        select(Task.id, Task.title)
        .where(Task.title.ilike(f"{q}%"))
        .limit(limit)
    )
    for row in tasks_result:
        suggestions.append(
            SearchSuggestion(type="task", id=row.id, title=row.title)
        )

    users_result = await db.execute(
        select(User.id, User.username, User.full_name)
        .where(
            or_(
                User.username.ilike(f"{q}%"),
                User.full_name.ilike(f"{q}%"),
            )
        )
        .limit(limit)
    )
    for row in users_result:
        suggestions.append(
            SearchSuggestion(
                type="user", id=row.id, title=row.full_name or row.username
            )
        )

    return suggestions[:limit]


@router.post("/reindex/{entity_type}", response_model=ReindexResponse)
async def reindex_entity(
    entity_type: str,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> ReindexResponse:
    """Reindex all documents of a given entity type into Elasticsearch.

    Requires authentication. Supported entity types: projects, tasks, users.
    """
    await get_current_user(token, db)

    es = get_elasticsearch_service()
    if not es or not es.is_available:
        raise HTTPException(
            status_code=503,
            detail="Elasticsearch is not available",
        )

    valid_types = {"projects", "tasks", "users"}
    if entity_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid entity type. Must be one of: {', '.join(valid_types)}",
        )

    documents = []

    if entity_type == "projects":
        result = await db.execute(select(Project))
        for project in result.scalars():
            documents.append({
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "status": project.status,
                "priority": project.priority,
                "organization_id": project.organization_id,
                "created_by": project.created_by,
                "created_at": project.created_at.isoformat() if project.created_at else None,
                "updated_at": project.updated_at.isoformat() if project.updated_at else None,
            })

    elif entity_type == "tasks":
        result = await db.execute(
            select(Task, Project.organization_id)
            .join(Project, Task.project_id == Project.id)
        )
        for row in result:
            task = row[0]
            org_id = row[1]
            documents.append({
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "status": task.status,
                "priority": task.priority,
                "project_id": task.project_id,
                "organization_id": org_id,
                "assigned_to": task.assigned_to,
                "created_by": task.created_by,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None,
            })

    elif entity_type == "users":
        result = await db.execute(select(User))
        for u in result.scalars():
            documents.append({
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "full_name": u.full_name,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            })

    bulk_result = await es.bulk_index(entity_type, documents)
    return ReindexResponse(
        entity_type=entity_type,
        indexed=bulk_result["indexed"],
        errors=bulk_result["errors"],
    )
