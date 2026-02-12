from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List

from ..database import get_db
from ..models import Organization, User, user_organization
from ..schemas import OrganizationCreate, OrganizationResponse, UserResponse
from ..routers.auth import oauth2_scheme, get_current_user

router = APIRouter(prefix="/api/organizations", tags=["organizations"])

@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an organization",
    responses={400: {"description": "Organization slug already exists"}},
)
async def create_organization(
    org_data: OrganizationCreate,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Create a new organization.

    The slug must be unique. The authenticated user is automatically added as
    the first member.
    """
    current_user = await get_current_user(token, db)
    
    # Check if slug already exists
    existing = await db.execute(
        select(Organization).where(Organization.slug == org_data.slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization slug already exists"
        )
    
    # Create organization
    new_org = Organization(
        name=org_data.name,
        slug=org_data.slug,
        description=org_data.description,
        website=org_data.website
    )
    
    # Add creator as member
    new_org.members.append(current_user)
    
    db.add(new_org)
    await db.commit()
    await db.refresh(new_org)
    
    return new_org

@router.get(
    "/{organization_id}",
    response_model=OrganizationResponse,
    summary="Get organization details",
    responses={404: {"description": "Organization not found"}},
)
async def get_organization(
    organization_id: int,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve details of a specific organization by its ID."""
    await get_current_user(token, db)
    
    result = await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    org = result.scalar_one_or_none()
    
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    return org

@router.get(
    "",
    response_model=List[OrganizationResponse],
    summary="List organizations",
)
async def list_organizations(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of records to return"),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """List all organizations the authenticated user belongs to."""
    current_user = await get_current_user(token, db)
    
    query = select(Organization).where(
        Organization.members.any(User.id == current_user.id)
    ).offset(skip).limit(limit)
    
    result = await db.execute(query)
    orgs = result.scalars().all()
    
    return orgs

@router.get(
    "/{organization_id}/members",
    response_model=List[UserResponse],
    summary="List organization members",
    responses={404: {"description": "Organization not found"}},
)
async def get_organization_members(
    organization_id: int,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of records to return"),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve the list of members belonging to an organization."""
    await get_current_user(token, db)
    
    result = await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    org = result.scalar_one_or_none()
    
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    return org.members[skip:skip+limit]

@router.post(
    "/{organization_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Add a member to an organization",
    responses={404: {"description": "Organization or user not found"}},
)
async def add_member(
    organization_id: int,
    user_id: int,
    role: str = Query('member', description="Member role (e.g. owner, admin, member, viewer)"),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Add a user to an organization with the specified role."""
    current_user = await get_current_user(token, db)
    
    org_result = await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    org = org_result.scalar_one_or_none()
    
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    user_result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if user not in org.members:
        org.members.append(user)
        await db.commit()

@router.delete(
    "/{organization_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a member from an organization",
    responses={404: {"description": "Organization not found"}},
)
async def remove_member(
    organization_id: int,
    user_id: int,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Remove a user from an organization."""
    current_user = await get_current_user(token, db)
    
    org_result = await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    org = org_result.scalar_one_or_none()
    
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    user_result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = user_result.scalar_one_or_none()
    
    if user and user in org.members:
        org.members.remove(user)
        await db.commit()