"""Role-Based Access Control (RBAC) module for the enterprise platform.

Defines role enums, role hierarchies, and permission-checking utilities
for organization-level and project-level access control.
"""

from enum import Enum
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User, user_organization, project_team, Project


class OrganizationRole(str, Enum):
    """Organization-level roles with hierarchical permissions."""
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class ProjectRole(str, Enum):
    """Project-level roles."""
    ADMIN = "admin"
    CONTRIBUTOR = "contributor"
    VIEWER = "viewer"


# Role hierarchy: higher value = more permissions
ORG_ROLE_HIERARCHY: dict[OrganizationRole, int] = {
    OrganizationRole.VIEWER: 0,
    OrganizationRole.MEMBER: 1,
    OrganizationRole.ADMIN: 2,
    OrganizationRole.OWNER: 3,
}

PROJECT_ROLE_HIERARCHY: dict[ProjectRole, int] = {
    ProjectRole.VIEWER: 0,
    ProjectRole.CONTRIBUTOR: 1,
    ProjectRole.ADMIN: 2,
}


async def get_user_org_role(
    user_id: int,
    organization_id: int,
    db: AsyncSession,
) -> Optional[OrganizationRole]:
    """Get a user's role in an organization.

    Returns None if the user is not a member.
    """
    result = await db.execute(
        select(user_organization.c.role).where(
            user_organization.c.user_id == user_id,
            user_organization.c.organization_id == organization_id,
        )
    )
    role_value = result.scalar_one_or_none()
    if role_value is None:
        return None
    try:
        return OrganizationRole(role_value)
    except ValueError:
        return OrganizationRole.MEMBER


async def get_user_project_role(
    user_id: int,
    project_id: int,
    db: AsyncSession,
) -> Optional[ProjectRole]:
    """Get a user's role in a project.

    Returns None if the user is not a project member.
    """
    result = await db.execute(
        select(project_team.c.role).where(
            project_team.c.user_id == user_id,
            project_team.c.project_id == project_id,
        )
    )
    role_value = result.scalar_one_or_none()
    if role_value is None:
        return None
    try:
        return ProjectRole(role_value)
    except ValueError:
        return ProjectRole.CONTRIBUTOR


def require_superuser(user: User) -> User:
    """Verify that the user is a superuser. Raises 403 if not."""
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser access required",
        )
    return user


async def require_org_role(
    user: User,
    organization_id: int,
    db: AsyncSession,
    minimum_role: OrganizationRole,
) -> OrganizationRole:
    """Verify user has at least the minimum role in an organization.

    Superusers bypass all role checks.
    Raises 403 if the user lacks sufficient permissions.
    """
    if user.is_superuser:
        return OrganizationRole.OWNER

    role = await get_user_org_role(user.id, organization_id, db)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )

    if ORG_ROLE_HIERARCHY[role] < ORG_ROLE_HIERARCHY[minimum_role]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires at least '{minimum_role.value}' role in this organization",
        )

    return role


async def require_project_role(
    user: User,
    project_id: int,
    db: AsyncSession,
    minimum_role: ProjectRole,
) -> ProjectRole:
    """Verify user has at least the minimum role in a project.

    Superusers bypass all role checks.
    Falls back to organization role if the user is not a direct project member.
    Raises 403 if the user lacks sufficient permissions.
    """
    if user.is_superuser:
        return ProjectRole.ADMIN

    role = await get_user_project_role(user.id, project_id, db)
    if role is not None:
        if PROJECT_ROLE_HIERARCHY[role] < PROJECT_ROLE_HIERARCHY[minimum_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires at least '{minimum_role.value}' role in this project",
            )
        return role

    # Fallback: check organization-level role via the project's organization
    result = await db.execute(
        select(Project.organization_id).where(Project.id == project_id)
    )
    org_id = result.scalar_one_or_none()
    if org_id is not None:
        org_role = await get_user_org_role(user.id, org_id, db)
        if org_role is not None:
            # Map org roles to project-level equivalent
            if ORG_ROLE_HIERARCHY[org_role] >= ORG_ROLE_HIERARCHY[OrganizationRole.ADMIN]:
                return ProjectRole.ADMIN
            if ORG_ROLE_HIERARCHY[org_role] >= ORG_ROLE_HIERARCHY[OrganizationRole.MEMBER]:
                if PROJECT_ROLE_HIERARCHY[ProjectRole.CONTRIBUTOR] >= PROJECT_ROLE_HIERARCHY[minimum_role]:
                    return ProjectRole.CONTRIBUTOR
            if PROJECT_ROLE_HIERARCHY[ProjectRole.VIEWER] >= PROJECT_ROLE_HIERARCHY[minimum_role]:
                return ProjectRole.VIEWER

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not a member of this project",
    )
