from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from typing import List

from ..database import get_db
from ..models import EmailNotificationPreference
from ..schemas import (
    EmailNotificationPreferenceResponse,
    EmailNotificationPreferenceUpdate,
    EmailSendRequest,
    EmailSendResponse,
)
from ..email_service import email_service
from ..routers.auth import oauth2_scheme, get_current_user

router = APIRouter(prefix="/api/email-notifications", tags=["email-notifications"])


@router.get("/preferences", response_model=EmailNotificationPreferenceResponse)
async def get_email_preferences(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Get email notification preferences for the current user."""
    current_user = await get_current_user(token, db)

    result = await db.execute(
        select(EmailNotificationPreference).where(
            EmailNotificationPreference.user_id == current_user.id
        )
    )
    prefs = result.scalar_one_or_none()

    if not prefs:
        # Create default preferences
        prefs = EmailNotificationPreference(user_id=current_user.id)
        db.add(prefs)
        await db.commit()
        await db.refresh(prefs)

    return prefs


@router.put("/preferences", response_model=EmailNotificationPreferenceResponse)
async def update_email_preferences(
    preferences: EmailNotificationPreferenceUpdate,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Update email notification preferences for the current user."""
    current_user = await get_current_user(token, db)

    result = await db.execute(
        select(EmailNotificationPreference).where(
            EmailNotificationPreference.user_id == current_user.id
        )
    )
    prefs = result.scalar_one_or_none()

    if not prefs:
        prefs = EmailNotificationPreference(user_id=current_user.id)
        db.add(prefs)

    prefs.email_enabled = preferences.email_enabled
    prefs.task_assigned = preferences.task_assigned
    prefs.task_updated = preferences.task_updated
    prefs.comment_added = preferences.comment_added
    prefs.project_invitation = preferences.project_invitation
    prefs.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(prefs)

    return prefs


@router.post("/send", response_model=EmailSendResponse)
async def send_email_notification(
    request: EmailSendRequest,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Send an email notification. Requires authentication."""
    await get_current_user(token, db)

    success = email_service.send_notification(
        to_email=request.to_email,
        notification_type=request.notification_type,
        context=request.context,
    )

    if success:
        return EmailSendResponse(success=True, message="Email sent successfully")

    return EmailSendResponse(
        success=False,
        message="Email sending is disabled or failed. Check server configuration.",
    )


@router.get("/types")
async def get_notification_types(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Get supported email notification types."""
    await get_current_user(token, db)
    return {"notification_types": email_service.get_supported_notification_types()}
