from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List

from ..database import get_db
from ..models import Organization, User, user_organization
from ..schemas import OrganizationCreate, OrganizationResponse, UserResponse
from ..routers.auth import oauth2_scheme, get_current_user

router = APIRouter(prefix="/api/organizations", tags=["organizations"])

@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    organization_data: OrganizationCreate,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Create new organization"""
    current_user = await get_current_user(token, db)

    # Check if slug already exists
    existing = await db.execute(
        select(Organization).where(Organization.slug == organization_data.slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization slug already exists"
        )

    # Create organization
    new_organization = Organization(
        name=organization_data.name,
        slug=organization_data.slug,
        description=organization_data.description,
        website=organization_data.website
    )

    # Add creator as member
    new_organization.members.append(current_user)

    db.add(new_organization)
    await db.commit()
    await db.refresh(new_organization)

    return new_organization

@router.get("/{organization_id}", response_model=OrganizationResponse)
async def get_organization(
    organization_id: int,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Get organization details"""
    await get_current_user(token, db)

    organization_query = await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    organization = organization_query.scalar_one_or_none()

    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )

    return organization

@router.get("", response_model=List[OrganizationResponse])
async def list_organizations(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """List all organizations for current user"""
    current_user = await get_current_user(token, db)

    query = select(Organization).where(
        Organization.members.any(User.id == current_user.id)
    ).offset(skip).limit(limit)

    organizations_query = await db.execute(query)
    organizations = organizations_query.scalars().all()

    return organizations

@router.get("/{organization_id}/members", response_model=List[UserResponse])
async def get_organization_members(
    organization_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Get organization members"""
    await get_current_user(token, db)

    organization_query = await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    organization = organization_query.scalar_one_or_none()

    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )

    return organization.members[skip:skip+limit]

@router.post("/{organization_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def add_member(
    organization_id: int,
    user_id: int,
    role: str = Query('member'),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Add member to organization"""
    current_user = await get_current_user(token, db)

    organization_query = await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    organization = organization_query.scalar_one_or_none()

    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )

    user_query = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = user_query.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if user not in organization.members:
        organization.members.append(user)
        await db.commit()

@router.delete("/{organization_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    organization_id: int,
    user_id: int,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Remove member from organization"""
    current_user = await get_current_user(token, db)

    organization_query = await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    organization = organization_query.scalar_one_or_none()

    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )

    user_query = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = user_query.scalar_one_or_none()

    if user and user in organization.members:
        organization.members.remove(user)
        await db.commit()