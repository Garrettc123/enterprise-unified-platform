from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, update
from datetime import datetime
from typing import List

from ..database import get_db
from ..models import Notification
from ..schemas import BaseModel
from ..routers.auth import oauth2_scheme, get_current_user

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

class NotificationCreate(BaseModel):
    title: str
    message: str
    notification_type: str

class NotificationResponse(BaseModel):
    id: int
    title: str
    message: str
    notification_type: str
    is_read: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

@router.get(
    "",
    response_model=List[NotificationResponse],
    summary="List notifications",
)
async def get_notifications(
    unread_only: bool = Query(False, description="Return only unread notifications"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of records to return"),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """List notifications for the authenticated user.

    Supports filtering to show only unread notifications and pagination.
    """
    current_user = await get_current_user(token, db)
    
    query = select(Notification).where(
        Notification.user_id == current_user.id
    )
    
    if unread_only:
        query = query.where(Notification.is_read == False)
    
    query = query.order_by(desc(Notification.created_at)).offset(skip).limit(limit)
    
    result = await db.execute(query)
    notifications = result.scalars().all()
    
    return notifications

@router.post(
    "/{notification_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark notification as read",
    responses={
        404: {"description": "Notification not found"},
        403: {"description": "Not authorized to access this notification"},
    },
)
async def mark_as_read(
    notification_id: int,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Mark a single notification as read."""
    current_user = await get_current_user(token, db)
    
    result = await db.execute(
        select(Notification).where(Notification.id == notification_id)
    )
    notification = result.scalar_one_or_none()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    if notification.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this notification"
        )
    
    notification.is_read = True
    notification.read_at = datetime.utcnow()
    await db.commit()

@router.post(
    "/mark-all-as-read",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark all notifications as read",
)
async def mark_all_as_read(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Mark all unread notifications as read for the authenticated user."""
    current_user = await get_current_user(token, db)
    
    stmt = update(Notification).where(
        (Notification.user_id == current_user.id) &
        (Notification.is_read == False)
    ).values(
        is_read=True,
        read_at=datetime.utcnow()
    )
    
    await db.execute(stmt)
    await db.commit()

@router.get(
    "/unread-count",
    summary="Get unread notification count",
)
async def get_unread_count(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Return the number of unread notifications for the authenticated user."""
    current_user = await get_current_user(token, db)
    
    result = await db.execute(
        select(func.count(Notification.id)).where(
            (Notification.user_id == current_user.id) &
            (Notification.is_read == False)
        )
    )
    count = result.scalar() or 0
    
    return {"unread_count": count}

from sqlalchemy import func