"""CRUD helper utilities to eliminate code duplication in routers."""

from typing import TypeVar, Type, Optional, List, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import DeclarativeMeta

ModelType = TypeVar("ModelType", bound=DeclarativeMeta)


async def get_entity_by_id(
    db: AsyncSession,
    model: Type[ModelType],
    entity_id: int,
    not_found_detail: str = "Entity not found"
) -> ModelType:
    """
    Fetch an entity by ID or raise 404 if not found.

    Args:
        db: Database session
        model: SQLAlchemy model class
        entity_id: ID of the entity to fetch
        not_found_detail: Error message for 404 response

    Returns:
        The entity instance

    Raises:
        HTTPException: 404 if entity not found
    """
    result = await db.execute(
        select(model).where(model.id == entity_id)
    )
    entity = result.scalar_one_or_none()

    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=not_found_detail
        )

    return entity


async def create_entity(
    db: AsyncSession,
    entity: ModelType
) -> ModelType:
    """
    Create a new entity in the database.

    Args:
        db: Database session
        entity: Entity instance to create

    Returns:
        The created entity with ID and timestamps
    """
    db.add(entity)
    await db.commit()
    await db.refresh(entity)
    return entity


async def update_entity_fields(
    db: AsyncSession,
    entity: ModelType,
    update_data: Dict[str, Any],
    exclude_none: bool = True
) -> ModelType:
    """
    Update entity fields from a dictionary.

    Args:
        db: Database session
        entity: Entity to update
        update_data: Dictionary of field names to values
        exclude_none: If True, skip None values

    Returns:
        Updated entity
    """
    for field, value in update_data.items():
        if exclude_none and value is None:
            continue
        if hasattr(entity, field):
            setattr(entity, field, value)

    await db.commit()
    await db.refresh(entity)
    return entity


async def delete_entity(
    db: AsyncSession,
    entity: ModelType
) -> None:
    """
    Delete an entity from the database.

    Args:
        db: Database session
        entity: Entity to delete
    """
    await db.delete(entity)
    await db.commit()


async def list_entities_with_filters(
    db: AsyncSession,
    model: Type[ModelType],
    filters: Optional[Dict[str, Any]] = None,
    skip: int = 0,
    limit: int = 10,
    order_by_field: Optional[str] = "created_at",
    order_desc: bool = True
) -> List[ModelType]:
    """
    List entities with optional filtering and pagination.

    Args:
        db: Database session
        model: SQLAlchemy model class
        filters: Dictionary of field names to filter values (None values are ignored)
        skip: Number of records to skip
        limit: Maximum number of records to return
        order_by_field: Field name to order by
        order_desc: If True, order descending

    Returns:
        List of entities matching filters
    """
    query = select(model)

    # Apply filters
    if filters:
        for field, value in filters.items():
            if value is not None and hasattr(model, field):
                query = query.where(getattr(model, field) == value)

    # Apply ordering
    if order_by_field and hasattr(model, order_by_field):
        order_field = getattr(model, order_by_field)
        if order_desc:
            query = query.order_by(desc(order_field))
        else:
            query = query.order_by(order_field)

    # Apply pagination
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


async def verify_user_access(
    db: AsyncSession,
    user_id: int,
    resource: ModelType,
    access_field: str = "created_by",
    error_detail: str = "Access denied"
) -> None:
    """
    Verify that a user has access to a resource.

    Args:
        db: Database session
        user_id: ID of the user to check
        resource: Resource entity to check access for
        access_field: Field name containing the user ID (e.g., "created_by", "owner_id")
        error_detail: Error message for 403 response

    Raises:
        HTTPException: 403 if user doesn't have access
    """
    if not hasattr(resource, access_field):
        return  # No access control on this field

    if getattr(resource, access_field) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_detail
        )
