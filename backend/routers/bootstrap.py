"""One-time, environment-gated first administrator bootstrap.

Required backend environment variables:
- ADMIN_BOOTSTRAP_EMAIL: the exact owner email allowed to bootstrap.
- ADMIN_BOOTSTRAP_TOKEN: a random secret of at least 32 characters, stored only
  in the backend's secret manager.

This endpoint is intentionally unavailable unless both values are configured. It only works
while the user table is empty, and it never returns the submitted password or password hash.
"""
import hmac
import os

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import User
from ..schemas import UserCreate, UserResponse
from ..security import get_password_hash

router = APIRouter(prefix="/api/auth", tags=["auth-bootstrap"])


class BootstrapAdminCreate(UserCreate):
    """Stricter password policy for the one-time owner bootstrap."""

    password: str = Field(..., min_length=12, max_length=72)


class BootstrapAdminResponse(UserResponse):
    """Return the created user's role without returning password material."""

    is_superuser: bool


@router.post(
    "/bootstrap-admin",
    response_model=BootstrapAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
async def bootstrap_first_admin(
    user_data: BootstrapAdminCreate,
    x_admin_bootstrap_token: str | None = Header(default=None, alias="X-Admin-Bootstrap-Token"),
    db: AsyncSession = Depends(get_db),
):
    """Create the first and only bootstrap administrator; fail closed by default."""
    configured_email = os.getenv("ADMIN_BOOTSTRAP_EMAIL", "").strip().lower()
    configured_token = os.getenv("ADMIN_BOOTSTRAP_TOKEN", "")

    if not configured_email or len(configured_token) < 32:
        raise HTTPException(status_code=503, detail="First-admin bootstrap is not configured")

    if not x_admin_bootstrap_token or not hmac.compare_digest(
        x_admin_bootstrap_token, configured_token
    ):
        raise HTTPException(status_code=403, detail="Bootstrap authorization failed")

    if user_data.email.strip().lower() != configured_email:
        raise HTTPException(status_code=403, detail="Email is not authorized for bootstrap")

    # bcrypt accepts at most 72 UTF-8 bytes; reject rather than silently truncating.
    if len(user_data.password.encode("utf-8")) > 72:
        raise HTTPException(status_code=422, detail="Password must be at most 72 UTF-8 bytes")

    count_result = await db.execute(select(func.count(User.id)))
    if int(count_result.scalar_one()) != 0:
        raise HTTPException(
            status_code=409,
            detail="Bootstrap is closed because an account already exists",
        )

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
    except IntegrityError:
        # Also closes the simultaneous-request race via the database's unique email constraint.
        await db.rollback()
        raise HTTPException(status_code=409, detail="Bootstrap was already completed")
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Administrator setup failed; check backend logs and database connectivity",
        )

    return new_admin
