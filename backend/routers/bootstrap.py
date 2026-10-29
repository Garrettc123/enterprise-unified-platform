"""One-time, environment-gated first administrator bootstrap.

Required backend environment variables:
- ADMIN_BOOTSTRAP_EMAIL: the exact owner email allowed to bootstrap.
- ADMIN_BOOTSTRAP_TOKEN: a long random secret stored only in the backend secret manager.

This endpoint is intentionally unavailable unless both values are configured. It only works
while the user table is empty, and it never returns the submitted password or password hash.
"""
import hmac
import os

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import User
from ..schemas import UserCreate, UserResponse
from ..security import get_password_hash

router = APIRouter(prefix="/api/auth", tags=["auth-bootstrap"])


@router.post("/bootstrap-admin", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def bootstrap_first_admin(
    user_data: UserCreate,
    x_admin_bootstrap_token: str | None = Header(default=None, alias="X-Admin-Bootstrap-Token"),
    db: AsyncSession = Depends(get_db),
):
    """Create the first and only bootstrap administrator; fail closed by default."""
    configured_email = os.getenv("ADMIN_BOOTSTRAP_EMAIL", "").strip().lower()
    configured_token = os.getenv("ADMIN_BOOTSTRAP_TOKEN", "")

    if not configured_email or not configured_token:
        raise HTTPException(status_code=503, detail="First-admin bootstrap is not configured")

    if not x_admin_bootstrap_token or not hmac.compare_digest(
        x_admin_bootstrap_token, configured_token
    ):
        raise HTTPException(status_code=403, detail="Bootstrap authorization failed")

    if user_data.email.strip().lower() != configured_email:
        raise HTTPException(status_code=403, detail="Email is not authorized for bootstrap")

    count_result = await db.execute(select(func.count(User.id)))
    user_count = int(count_result.scalar_one())
    if user_count != 0:
        raise HTTPException(status_code=409, detail="Bootstrap is closed because an account already exists")

    new_admin = User(
        email=configured_email,
        username=user_data.username,
        full_name=user_data.full_name,
        hashed_password=get_password_hash(user_data.password),
        is_active=True,
        is_superuser=True,
    )
    db.add(new_admin)
    try:
        await db.commit()
        await db.refresh(new_admin)
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Account could not be created; verify the database state")

    return new_admin
