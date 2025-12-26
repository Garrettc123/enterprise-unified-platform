from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List
from datetime import datetime, timedelta

from ..database import get_db
from ..models import AuditLog, Organization, User
from ..schemas import BaseModel
from ..routers.auth import oauth2_scheme, get_current_user

router = APIRouter(prefix="/api/audit", tags=["audit"])

class AuditLogResponse(BaseModel):
    id: int
    user_id: int
    action: str
    entity_type: str
    entity_id: int
    changes: dict
    ip_address: str
    user_agent: str
    created_at: datetime
    
    class Config:
        from_attributes = True

@router.get("/logs", response_model=List[AuditLogResponse])
async def get_audit_logs(
    organization_id: int = Query(...),
    days: int = Query(30, ge=1, le=365),
    action: str = Query(None),
    entity_type: str = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Get audit logs for organization"""
    current_user = await get_current_user(token, db)
    
    # Verify user belongs to organization
    org_result = await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    org = org_result.scalar_one_or_none()
    if not org or current_user not in org.members:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view audit logs"
        )
    
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    query = select(AuditLog).where(
        AuditLog.created_at >= cutoff_date
    )
    
    if action:
        query = query.where(AuditLog.action == action)
    
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    
    query = query.order_by(desc(AuditLog.created_at)).offset(skip).limit(limit)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return logs

@router.get("/logs/user/{user_id}", response_model=List[AuditLogResponse])
async def get_user_audit_logs(
    user_id: int,
    days: int = Query(30, ge=1, le=365),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Get audit logs for specific user"""
    await get_current_user(token, db)
    
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    query = select(AuditLog).where(
        (AuditLog.user_id == user_id) &
        (AuditLog.created_at >= cutoff_date)
    ).order_by(desc(AuditLog.created_at)).offset(skip).limit(limit)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return logs

@router.get("/summary")
async def get_audit_summary(
    organization_id: int = Query(...),
    days: int = Query(30, ge=1, le=365),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Get audit summary statistics"""
    current_user = await get_current_user(token, db)
    
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Get total actions
    total_result = await db.execute(
        select(func.count(AuditLog.id)).where(
            AuditLog.created_at >= cutoff_date
        )
    )
    total_actions = total_result.scalar() or 0
    
    # Get actions by type
    actions_result = await db.execute(
        select(
            AuditLog.action,
            func.count(AuditLog.id)
        ).where(
            AuditLog.created_at >= cutoff_date
        ).group_by(AuditLog.action)
    )
    
    actions_by_type = {}
    for row in actions_result.all():
        actions_by_type[row[0]] = row[1]
    
    return {
        "total_actions": total_actions,
        "actions_by_type": actions_by_type,
        "days_covered": days
    }

from sqlalchemy import func
from fastapi import HTTPException, status