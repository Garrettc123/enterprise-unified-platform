from fastapi import APIRouter, Depends, Query, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import csv
import json
from io import StringIO
from datetime import datetime
from typing import List, Optional

from ..database import get_db
from ..models import Project, Task, Organization
from ..schemas import ImportResult
from ..routers.auth import oauth2_scheme, get_current_user

router = APIRouter(prefix="/api/import", tags=["import"])

VALID_PROJECT_STATUSES = {"active", "archived", "completed"}
VALID_PROJECT_PRIORITIES = {"low", "medium", "high", "critical"}
VALID_TASK_STATUSES = {"todo", "in_progress", "in_review", "completed", "blocked"}
VALID_TASK_PRIORITIES = {"low", "medium", "high", "critical"}


def _parse_float(value: str) -> Optional[float]:
    """Parse a string to float, returning None for empty strings."""
    if not value or value.strip() == "":
        return None
    return float(value)


def _parse_int(value: str) -> Optional[int]:
    """Parse a string to int, returning None for empty strings."""
    if not value or value.strip() == "":
        return None
    return int(value)


def _parse_datetime(value: str) -> Optional[datetime]:
    """Parse an ISO format datetime string, returning None for empty strings."""
    if not value or value.strip() == "":
        return None
    return datetime.fromisoformat(value)


@router.post("/projects/csv", response_model=ImportResult)
async def import_projects_csv(
    organization_id: int = Query(...),
    file: UploadFile = File(...),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Import projects from a CSV file.

    Expected CSV columns: Name, Description, Status, Priority, Budget
    """
    current_user = await get_current_user(token, db)

    # Verify organization exists
    org_result = await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    if not org_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Read and parse CSV
    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be UTF-8 encoded",
        )

    reader = csv.DictReader(StringIO(text))
    imported = 0
    errors: List[str] = []

    for row_num, row in enumerate(reader, start=2):  # start=2 because row 1 is the header
        try:
            name = row.get("Name", "").strip()
            if not name:
                errors.append(f"Row {row_num}: Name is required")
                continue

            project_status = row.get("Status", "active").strip() or "active"
            if project_status not in VALID_PROJECT_STATUSES:
                errors.append(f"Row {row_num}: Invalid status '{project_status}'")
                continue

            priority = row.get("Priority", "medium").strip() or "medium"
            if priority not in VALID_PROJECT_PRIORITIES:
                errors.append(f"Row {row_num}: Invalid priority '{priority}'")
                continue

            budget = _parse_float(row.get("Budget", ""))

            project = Project(
                name=name,
                description=row.get("Description", "").strip() or None,
                organization_id=organization_id,
                created_by=current_user.id,
                status=project_status,
                priority=priority,
                budget=budget,
            )
            db.add(project)
            imported += 1
        except (ValueError, KeyError) as e:
            errors.append(f"Row {row_num}: {str(e)}")

    if imported > 0:
        await db.commit()

    return ImportResult(
        imported_count=imported,
        errors=errors,
        total_rows=imported + len(errors),
    )


@router.post("/tasks/csv", response_model=ImportResult)
async def import_tasks_csv(
    project_id: int = Query(...),
    file: UploadFile = File(...),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Import tasks from a CSV file.

    Expected CSV columns: Title, Description, Status, Priority, Assigned To, Due Date, Story Points
    """
    current_user = await get_current_user(token, db)

    # Verify project exists
    proj_result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    if not proj_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be UTF-8 encoded",
        )

    reader = csv.DictReader(StringIO(text))
    imported = 0
    errors: List[str] = []

    for row_num, row in enumerate(reader, start=2):  # start=2 because row 1 is the header
        try:
            title = row.get("Title", "").strip()
            if not title:
                errors.append(f"Row {row_num}: Title is required")
                continue

            task_status = row.get("Status", "todo").strip() or "todo"
            if task_status not in VALID_TASK_STATUSES:
                errors.append(f"Row {row_num}: Invalid status '{task_status}'")
                continue

            priority = row.get("Priority", "medium").strip() or "medium"
            if priority not in VALID_TASK_PRIORITIES:
                errors.append(f"Row {row_num}: Invalid priority '{priority}'")
                continue

            task = Task(
                title=title,
                description=row.get("Description", "").strip() or None,
                project_id=project_id,
                created_by=current_user.id,
                status=task_status,
                priority=priority,
                assigned_to=_parse_int(row.get("Assigned To", "")),
                due_date=_parse_datetime(row.get("Due Date", "")),
                story_points=_parse_int(row.get("Story Points", "")),
            )
            db.add(task)
            imported += 1
        except (ValueError, KeyError) as e:
            errors.append(f"Row {row_num}: {str(e)}")

    if imported > 0:
        await db.commit()

    return ImportResult(
        imported_count=imported,
        errors=errors,
        total_rows=imported + len(errors),
    )


@router.post("/projects/json", response_model=ImportResult)
async def import_projects_json(
    organization_id: int = Query(...),
    file: UploadFile = File(...),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Import projects from a JSON file.

    Expected JSON: array of objects with keys: name, description, status, priority, budget
    """
    current_user = await get_current_user(token, db)

    # Verify organization exists
    org_result = await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    if not org_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    content = await file.read()
    try:
        data = json.loads(content.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON file",
        )

    if not isinstance(data, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="JSON file must contain an array of objects",
        )

    imported = 0
    errors: List[str] = []

    for idx, item in enumerate(data):
        try:
            if not isinstance(item, dict):
                errors.append(f"Item {idx + 1}: Must be an object")
                continue

            name = str(item.get("name", "")).strip()
            if not name:
                errors.append(f"Item {idx + 1}: name is required")
                continue

            project_status = str(item.get("status", "active")).strip() or "active"
            if project_status not in VALID_PROJECT_STATUSES:
                errors.append(f"Item {idx + 1}: Invalid status '{project_status}'")
                continue

            priority = str(item.get("priority", "medium")).strip() or "medium"
            if priority not in VALID_PROJECT_PRIORITIES:
                errors.append(f"Item {idx + 1}: Invalid priority '{priority}'")
                continue

            budget = item.get("budget")
            if budget is not None:
                budget = float(budget)

            project = Project(
                name=name,
                description=str(item.get("description", "")).strip() or None,
                organization_id=organization_id,
                created_by=current_user.id,
                status=project_status,
                priority=priority,
                budget=budget,
            )
            db.add(project)
            imported += 1
        except (ValueError, TypeError) as e:
            errors.append(f"Item {idx + 1}: {str(e)}")

    if imported > 0:
        await db.commit()

    return ImportResult(
        imported_count=imported,
        errors=errors,
        total_rows=imported + len(errors),
    )


@router.post("/tasks/json", response_model=ImportResult)
async def import_tasks_json(
    project_id: int = Query(...),
    file: UploadFile = File(...),
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Import tasks from a JSON file.

    Expected JSON: array of objects with keys: title, description, status, priority,
    assigned_to, due_date, story_points
    """
    current_user = await get_current_user(token, db)

    # Verify project exists
    proj_result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    if not proj_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    content = await file.read()
    try:
        data = json.loads(content.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON file",
        )

    if not isinstance(data, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="JSON file must contain an array of objects",
        )

    imported = 0
    errors: List[str] = []

    for idx, item in enumerate(data):
        try:
            if not isinstance(item, dict):
                errors.append(f"Item {idx + 1}: Must be an object")
                continue

            title = str(item.get("title", "")).strip()
            if not title:
                errors.append(f"Item {idx + 1}: title is required")
                continue

            task_status = str(item.get("status", "todo")).strip() or "todo"
            if task_status not in VALID_TASK_STATUSES:
                errors.append(f"Item {idx + 1}: Invalid status '{task_status}'")
                continue

            priority = str(item.get("priority", "medium")).strip() or "medium"
            if priority not in VALID_TASK_PRIORITIES:
                errors.append(f"Item {idx + 1}: Invalid priority '{priority}'")
                continue

            due_date = item.get("due_date")
            if due_date:
                due_date = datetime.fromisoformat(str(due_date))

            assigned_to = item.get("assigned_to")
            if assigned_to is not None:
                assigned_to = int(assigned_to)

            story_points = item.get("story_points")
            if story_points is not None:
                story_points = int(story_points)

            task = Task(
                title=title,
                description=str(item.get("description", "")).strip() or None,
                project_id=project_id,
                created_by=current_user.id,
                status=task_status,
                priority=priority,
                assigned_to=assigned_to,
                due_date=due_date,
                story_points=story_points,
            )
            db.add(task)
            imported += 1
        except (ValueError, TypeError) as e:
            errors.append(f"Item {idx + 1}: {str(e)}")

    if imported > 0:
        await db.commit()

    return ImportResult(
        imported_count=imported,
        errors=errors,
        total_rows=imported + len(errors),
    )
