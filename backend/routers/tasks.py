from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from datetime import datetime
from typing import List

from ..database import get_db
from ..models import Task, Project, Comment, User
from ..schemas import TaskCreate, TaskResponse, CommentCreate, CommentResponse
from ..routers.auth import oauth2_scheme, get_current_user

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Create new task in project"""
    current_user = await get_current_user(token, db)
    
    # Verify project exists
    project_result = await db.execute(
        select(Project).where(Project.id == task_data.project_id)
    )
    project = project_result.scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Create task
    new_task = Task(
        title=task_data.title,
        description=task_data.description,
        project_id=task_data.project_id,
        assigned_to=task_data.assigned_to,
        created_by=current_user.id,
        status=task_data.status,
        priority=task_data.priority,
        story_points=task_data.story_points
    )
    
    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)
    
    return new_task

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Get task details"""
    await get_current_user(token, db)
    
    result = await db.execute(
        select(Task).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    return task

@router.get("", response_model=List[TaskResponse])
async def list_tasks(
    project_id: int = Query(...),
    status: str = Query(None),
    assigned_to: int = Query(None),
    priority: str = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """List tasks with advanced filtering"""
    await get_current_user(token, db)
    
    query = select(Task).where(Task.project_id == project_id)
    
    if status:
        query = query.where(Task.status == status)
    
    if assigned_to:
        query = query.where(Task.assigned_to == assigned_to)
    
    if priority:
        query = query.where(Task.priority == priority)
    
    query = query.order_by(desc(Task.created_at)).offset(skip).limit(limit)
    result = await db.execute(query)
    tasks = result.scalars().all()
    
    return tasks

@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    task_data: TaskCreate,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Update task"""
    current_user = await get_current_user(token, db)
    
    result = await db.execute(
        select(Task).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Update fields
    if task_data.title:
        task.title = task_data.title
    if task_data.description:
        task.description = task_data.description
    if task_data.status:
        task.status = task_data.status
    if task_data.priority:
        task.priority = task_data.priority
    if task_data.story_points:
        task.story_points = task_data.story_points
    
    # Mark as completed
    if task_data.status == 'completed' and not task.completed_at:
        task.completed_at = datetime.utcnow()
    
    task.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(task)
    
    return task

@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Delete task"""
    current_user = await get_current_user(token, db)
    
    result = await db.execute(
        select(Task).where(Task.id == task_id)
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    await db.delete(task)
    await db.commit()

@router.post("/{task_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def add_comment(
    task_id: int,
    comment_data: CommentCreate,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Add comment to task"""
    current_user = await get_current_user(token, db)
    
    # Verify task exists
    task_result = await db.execute(
        select(Task).where(Task.id == task_id)
    )
    task = task_result.scalar_one_or_none()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Create comment
    new_comment = Comment(
        content=comment_data.content,
        task_id=task_id,
        created_by=current_user.id
    )
    
    db.add(new_comment)
    await db.commit()
    await db.refresh(new_comment)
    
    return new_comment

@router.get("/{task_id}/comments", response_model=List[CommentResponse])
async def get_comments(
    task_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Get comments for task"""
    await get_current_user(token, db)
    
    query = select(Comment).where(
        Comment.task_id == task_id
    ).order_by(desc(Comment.created_at)).offset(skip).limit(limit)
    
    result = await db.execute(query)
    comments = result.scalars().all()
    
    return comments