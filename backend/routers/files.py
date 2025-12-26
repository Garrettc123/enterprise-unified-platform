from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List
import os
import shutil
from datetime import datetime

from ..database import get_db
from ..models import Attachment, Task
from ..schemas import BaseModel
from ..routers.auth import oauth2_scheme, get_current_user

router = APIRouter(prefix="/api/files", tags=["files"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

class FileResponse(BaseModel):
    id: int
    filename: str
    file_size: int
    file_type: str
    task_id: int
    uploaded_by: int
    created_at: datetime
    
    class Config:
        from_attributes = True

@router.post("/upload/{task_id}", response_model=FileResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    task_id: int,
    file: UploadFile = File(...),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Upload file attachment to task"""
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
    
    # Validate file
    if file.size and file.size > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 50MB limit"
        )
    
    # Save file
    file_path = os.path.join(UPLOAD_DIR, f"{task_id}_{file.filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Get file size
    file_size = os.path.getsize(file_path)
    file_type = file.content_type or "application/octet-stream"
    
    # Create attachment record
    attachment = Attachment(
        filename=file.filename,
        file_path=file_path,
        file_size=file_size,
        file_type=file_type,
        task_id=task_id,
        uploaded_by=current_user.id
    )
    
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    
    return attachment

@router.get("/{attachment_id}")
async def download_file(
    attachment_id: int,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Download file attachment"""
    current_user = await get_current_user(token, db)
    
    result = await db.execute(
        select(Attachment).where(Attachment.id == attachment_id)
    )
    attachment = result.scalar_one_or_none()
    
    if not attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    if not os.path.exists(attachment.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found on disk"
        )
    
    return FileResponse(
        path=attachment.file_path,
        filename=attachment.filename
    )

@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    attachment_id: int,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Delete file attachment"""
    current_user = await get_current_user(token, db)
    
    result = await db.execute(
        select(Attachment).where(Attachment.id == attachment_id)
    )
    attachment = result.scalar_one_or_none()
    
    if not attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    
    # Delete from disk
    if os.path.exists(attachment.file_path):
        os.remove(attachment.file_path)
    
    # Delete record
    await db.delete(attachment)
    await db.commit()