from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List

from ..database import get_db
from ..models import Organization, User, user_organization
from ..schemas import OrganizationCreate, OrganizationResponse, UserResponse, RoleAssignment, RoleResponse
from ..routers.auth import oauth2_scheme, get_current_user
from ..rbac import OrganizationRole, require_org_role, get_user_org_role

router = APIRouter(prefix="/api/organizations", tags=["organizations"])

@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    org_data: OrganizationCreate,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Create new organization"""
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
    
    db.add(new_org)
    await db.flush()
    
    # Add creator as owner
    await db.execute(
        user_organization.insert().values(
            user_id=current_user.id,
            organization_id=new_org.id,
            role=OrganizationRole.OWNER.value,
        )
    )
    
    await db.commit()
    await db.refresh(new_org)
    
    return new_org

@router.get("/{organization_id}", response_model=OrganizationResponse)
async def get_organization(
    organization_id: int,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Get organization details"""
    current_user = await get_current_user(token, db)
    await require_org_role(current_user, organization_id, db, OrganizationRole.VIEWER)
    
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
    
    result = await db.execute(query)
    orgs = result.scalars().all()
    
    return orgs

@router.get("/{organization_id}/members", response_model=List[UserResponse])
async def get_organization_members(
    organization_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Get organization members"""
    current_user = await get_current_user(token, db)
    await require_org_role(current_user, organization_id, db, OrganizationRole.VIEWER)
    
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

@router.post("/{organization_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def add_member(
    organization_id: int,
    user_id: int,
    role: str = Query('member'),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Add member to organization (requires admin role)"""
    current_user = await get_current_user(token, db)
    await require_org_role(current_user, organization_id, db, OrganizationRole.ADMIN)
    
    # Validate role value
    try:
        validated_role = OrganizationRole(role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {', '.join(r.value for r in OrganizationRole)}"
        )
    
    # Only owners can assign the owner role
    if validated_role == OrganizationRole.OWNER:
        caller_role = await get_user_org_role(current_user.id, organization_id, db)
        if caller_role != OrganizationRole.OWNER and not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only owners can assign the owner role"
            )
    
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
    
    # Check if already a member
    existing = await db.execute(
        select(user_organization.c.role).where(
            user_organization.c.user_id == user_id,
            user_organization.c.organization_id == organization_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this organization"
        )
    
    await db.execute(
        user_organization.insert().values(
            user_id=user_id,
            organization_id=organization_id,
            role=validated_role.value,
        )
    )
    await db.commit()

@router.put("/{organization_id}/members/{user_id}/role", response_model=RoleResponse)
async def update_member_role(
    organization_id: int,
    user_id: int,
    role_data: RoleAssignment,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Update a member's role in an organization (requires admin role)"""
    current_user = await get_current_user(token, db)
    await require_org_role(current_user, organization_id, db, OrganizationRole.ADMIN)
    
    try:
        new_role = OrganizationRole(role_data.role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {', '.join(r.value for r in OrganizationRole)}"
        )
    
    # Only owners can assign or revoke the owner role
    if new_role == OrganizationRole.OWNER:
        caller_role = await get_user_org_role(current_user.id, organization_id, db)
        if caller_role != OrganizationRole.OWNER and not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only owners can assign the owner role"
            )
    
    # Verify membership exists
    existing = await db.execute(
        select(user_organization.c.role).where(
            user_organization.c.user_id == user_id,
            user_organization.c.organization_id == organization_id,
        )
    )
    if existing.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of this organization"
        )
    
    await db.execute(
        user_organization.update().where(
            user_organization.c.user_id == user_id,
            user_organization.c.organization_id == organization_id,
        ).values(role=new_role.value)
    )
    await db.commit()
    
    return {"user_id": user_id, "role": new_role.value}

@router.delete("/{organization_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    organization_id: int,
    user_id: int,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Remove member from organization (requires admin role)"""
    current_user = await get_current_user(token, db)
    await require_org_role(current_user, organization_id, db, OrganizationRole.ADMIN)
    
    # Prevent removing the last owner
    target_role = await get_user_org_role(user_id, organization_id, db)
    if target_role == OrganizationRole.OWNER:
        # Count remaining owners
        result = await db.execute(
            select(user_organization.c.user_id).where(
                user_organization.c.organization_id == organization_id,
                user_organization.c.role == OrganizationRole.OWNER.value,
            )
        )
        owners = result.scalars().all()
        if len(owners) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the last owner of an organization"
            )
    
    result = await db.execute(
        user_organization.delete().where(
            user_organization.c.user_id == user_id,
            user_organization.c.organization_id == organization_id,
        )
    )
    await db.commit()