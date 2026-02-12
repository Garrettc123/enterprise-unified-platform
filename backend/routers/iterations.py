from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from datetime import datetime
from typing import List

from ..database import get_db
from ..models import Iteration, Project, Task
from ..schemas import IterationCreate, IterationUpdate, IterationResponse, TaskResponse
from ..routers.auth import oauth2_scheme, get_current_user

router = APIRouter(prefix="/api/iterations", tags=["iterations"])

@router.post("", response_model=IterationResponse, status_code=status.HTTP_201_CREATED)
async def create_iteration(
    iteration_data: IterationCreate,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Create new iteration in project"""
    await get_current_user(token, db)

    # Verify project exists
    project_result = await db.execute(
        select(Project).where(Project.id == iteration_data.project_id)
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    if iteration_data.end_date <= iteration_data.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date must be after start date"
        )

    # Create iteration
    new_iteration = Iteration(
        name=iteration_data.name,
        description=iteration_data.description,
        project_id=iteration_data.project_id,
        start_date=iteration_data.start_date,
        end_date=iteration_data.end_date,
        status=iteration_data.status,
        goal=iteration_data.goal
    )

    db.add(new_iteration)
    await db.commit()
    await db.refresh(new_iteration)

    return new_iteration

@router.get("/{iteration_id}", response_model=IterationResponse)
async def get_iteration(
    iteration_id: int,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Get iteration details"""
    await get_current_user(token, db)

    result = await db.execute(
        select(Iteration).where(Iteration.id == iteration_id)
    )
    iteration = result.scalar_one_or_none()

    if not iteration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Iteration not found"
        )

    return iteration

@router.get("", response_model=List[IterationResponse])
async def list_iterations(
    project_id: int = Query(...),
    status: str = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """List iterations for a project"""
    await get_current_user(token, db)

    query = select(Iteration).where(Iteration.project_id == project_id)

    if status:
        query = query.where(Iteration.status == status)

    query = query.order_by(desc(Iteration.created_at)).offset(skip).limit(limit)
    result = await db.execute(query)
    iterations = result.scalars().all()

    return iterations

@router.patch("/{iteration_id}", response_model=IterationResponse)
async def update_iteration(
    iteration_id: int,
    iteration_data: IterationUpdate,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Update iteration"""
    await get_current_user(token, db)

    result = await db.execute(
        select(Iteration).where(Iteration.id == iteration_id)
    )
    iteration = result.scalar_one_or_none()

    if not iteration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Iteration not found"
        )

    # Update fields
    if iteration_data.name is not None:
        iteration.name = iteration_data.name
    if iteration_data.description is not None:
        iteration.description = iteration_data.description
    if iteration_data.start_date is not None:
        iteration.start_date = iteration_data.start_date
    if iteration_data.end_date is not None:
        iteration.end_date = iteration_data.end_date
    if iteration_data.status is not None:
        iteration.status = iteration_data.status
    if iteration_data.goal is not None:
        iteration.goal = iteration_data.goal

    iteration.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(iteration)

    return iteration

@router.delete("/{iteration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_iteration(
    iteration_id: int,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Delete iteration"""
    await get_current_user(token, db)

    result = await db.execute(
        select(Iteration).where(Iteration.id == iteration_id)
    )
    iteration = result.scalar_one_or_none()

    if not iteration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Iteration not found"
        )

    await db.delete(iteration)
    await db.commit()

@router.get("/{iteration_id}/tasks", response_model=List[TaskResponse])
async def get_iteration_tasks(
    iteration_id: int,
    status: str = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Get tasks assigned to an iteration"""
    await get_current_user(token, db)

    # Verify iteration exists
    iter_result = await db.execute(
        select(Iteration).where(Iteration.id == iteration_id)
    )
    iteration = iter_result.scalar_one_or_none()
    if not iteration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Iteration not found"
        )

    query = select(Task).where(Task.iteration_id == iteration_id)

    if status:
        query = query.where(Task.status == status)

    query = query.order_by(desc(Task.created_at)).offset(skip).limit(limit)
    result = await db.execute(query)
    tasks = result.scalars().all()

    return tasks
