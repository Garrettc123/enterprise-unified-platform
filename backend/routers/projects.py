from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from datetime import datetime
from typing import List

from ..database import get_db
from ..models import Project, Organization, User, Task
from ..schemas import ProjectCreate, ProjectResponse, TaskCreate, TaskResponse
from ..routers.auth import oauth2_scheme, get_current_user

router = APIRouter(prefix="/api/projects", tags=["projects"])

@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project",
    responses={404: {"description": "Organization not found"}},
)
async def create_project(
    project_data: ProjectCreate,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Create a new project within an organization.

    The specified organization must exist. The authenticated user is recorded
    as the project creator.
    """
    current_user = await get_current_user(token, db)
    
    # Verify organization exists and user has access
    org_result = await db.execute(
        select(Organization).where(Organization.id == project_data.organization_id)
    )
    organization = org_result.scalar_one_or_none()
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Create project
    new_project = Project(
        name=project_data.name,
        description=project_data.description,
        organization_id=project_data.organization_id,
        created_by=current_user.id,
        status=project_data.status,
        priority=project_data.priority,
        budget=project_data.budget
    )
    
    db.add(new_project)
    await db.commit()
    await db.refresh(new_project)
    
    return new_project

@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get project details",
    responses={404: {"description": "Project not found"}},
)
async def get_project(
    project_id: int,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve details of a specific project by its ID."""
    await get_current_user(token, db)
    
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    return project

@router.get(
    "",
    response_model=List[ProjectResponse],
    summary="List projects",
)
async def list_projects(
    organization_id: int = Query(..., description="Filter by organization ID"),
    status: str = Query(None, description="Filter by project status (e.g. active, completed, archived)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of records to return"),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """List projects in an organization with optional status filtering and pagination."""
    await get_current_user(token, db)
    
    query = select(Project).where(Project.organization_id == organization_id)
    
    if status:
        query = query.where(Project.status == status)
    
    query = query.order_by(desc(Project.created_at)).offset(skip).limit(limit)
    result = await db.execute(query)
    projects = result.scalars().all()
    
    return projects

@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update a project",
    responses={404: {"description": "Project not found"}},
)
async def update_project(
    project_id: int,
    project_data: ProjectCreate,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Update an existing project's details.

    All provided fields will overwrite the current values.
    """
    current_user = await get_current_user(token, db)
    
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Update fields
    project.name = project_data.name or project.name
    project.description = project_data.description or project.description
    project.status = project_data.status or project.status
    project.priority = project_data.priority or project.priority
    project.budget = project_data.budget or project.budget
    project.updated_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(project)
    
    return project

@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete (archive) a project",
    responses={404: {"description": "Project not found"}},
)
async def delete_project(
    project_id: int,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Archive a project by setting its status to 'archived'.

    This is a soft delete — the project data is preserved.
    """
    current_user = await get_current_user(token, db)
    
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Archive instead of delete
    project.status = 'archived'
    await db.commit()