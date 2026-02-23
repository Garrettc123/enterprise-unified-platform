from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from datetime import datetime
from typing import List

from ..database import get_db
from ..models import Project, Organization, User, Task
from ..schemas import ProjectCreate, ProjectResponse, TaskCreate, TaskResponse
from ..routers.auth import oauth2_scheme, get_current_user
from ..crud_helpers import get_entity_by_id, create_entity, update_entity_fields, list_entities_with_filters

router = APIRouter(prefix="/api/projects", tags=["projects"])

@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Create new project in organization"""
    current_user = await get_current_user(token, db)

    # Verify organization exists using helper
    organization = await get_entity_by_id(
        db, Organization, project_data.organization_id, "Organization not found"
    )

    # Create project using helper
    new_project = Project(
        name=project_data.name,
        description=project_data.description,
        organization_id=project_data.organization_id,
        created_by=current_user.id,
        status=project_data.status,
        priority=project_data.priority,
        budget=project_data.budget
    )

    return await create_entity(db, new_project)

@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Get project details"""
    await get_current_user(token, db)
    return await get_entity_by_id(db, Project, project_id, "Project not found")

@router.get("", response_model=List[ProjectResponse])
async def list_projects(
    organization_id: int = Query(...),
    status: str = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """List projects with filtering"""
    await get_current_user(token, db)

    return await list_entities_with_filters(
        db,
        Project,
        filters={"organization_id": organization_id, "status": status},
        skip=skip,
        limit=limit
    )

@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    project_data: ProjectCreate,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Update project"""
    current_user = await get_current_user(token, db)
    project = await get_entity_by_id(db, Project, project_id, "Project not found")

    # Update fields using helper
    update_data = {
        "name": project_data.name,
        "description": project_data.description,
        "status": project_data.status,
        "priority": project_data.priority,
        "budget": project_data.budget,
        "updated_at": datetime.utcnow()
    }

    return await update_entity_fields(db, project, update_data)

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Delete project (soft delete via archiving)"""
    current_user = await get_current_user(token, db)
    project = await get_entity_by_id(db, Project, project_id, "Project not found")

    # Archive instead of delete
    await update_entity_fields(db, project, {"status": "archived"})