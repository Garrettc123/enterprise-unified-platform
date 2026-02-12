from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, List


class UserBase(BaseModel):
    """Base schema for user data."""

    username: str = Field(
        ..., min_length=3, max_length=100, description="Unique username", examples=["johndoe"]
    )
    email: EmailStr = Field(..., description="User email address", examples=["john@example.com"])
    full_name: Optional[str] = Field(
        None, description="Full display name", examples=["John Doe"]
    )


class UserCreate(UserBase):
    """Schema for creating a new user account."""

    password: str = Field(
        ..., min_length=8, description="Password (minimum 8 characters)", examples=["securePass123"]
    )


class UserResponse(UserBase):
    """Schema for user data returned in API responses."""

    id: int = Field(..., description="Unique user identifier")
    is_active: bool = Field(..., description="Whether the user account is active")
    avatar_url: Optional[str] = Field(None, description="URL to user avatar image")
    bio: Optional[str] = Field(None, description="User biography")
    created_at: datetime = Field(..., description="Account creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        from_attributes = True


class OrganizationBase(BaseModel):
    """Base schema for organization data."""

    name: str = Field(
        ..., min_length=1, max_length=255, description="Organization name", examples=["Acme Corp"]
    )
    slug: str = Field(
        ..., min_length=1, max_length=255, description="URL-friendly identifier", examples=["acme-corp"]
    )
    description: Optional[str] = Field(None, description="Organization description")
    website: Optional[str] = Field(None, description="Organization website URL")


class OrganizationCreate(OrganizationBase):
    """Schema for creating a new organization."""

    pass


class OrganizationResponse(OrganizationBase):
    """Schema for organization data returned in API responses."""

    id: int = Field(..., description="Unique organization identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        from_attributes = True


class ProjectBase(BaseModel):
    """Base schema for project data."""

    name: str = Field(
        ..., min_length=1, max_length=255, description="Project name", examples=["Website Redesign"]
    )
    description: Optional[str] = Field(None, description="Project description")
    status: str = Field("active", description="Project status", examples=["active", "completed", "archived"])
    priority: str = Field("medium", description="Project priority level", examples=["low", "medium", "high", "critical"])
    budget: Optional[float] = Field(None, description="Project budget", examples=[50000.00])


class ProjectCreate(ProjectBase):
    """Schema for creating a new project."""

    organization_id: int = Field(..., description="ID of the parent organization")


class ProjectResponse(ProjectBase):
    """Schema for project data returned in API responses."""

    id: int = Field(..., description="Unique project identifier")
    organization_id: int = Field(..., description="ID of the parent organization")
    created_by: int = Field(..., description="ID of the user who created the project")
    start_date: Optional[datetime] = Field(None, description="Project start date")
    end_date: Optional[datetime] = Field(None, description="Project end date")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        from_attributes = True


class TaskBase(BaseModel):
    """Base schema for task data."""

    title: str = Field(
        ..., min_length=1, max_length=255, description="Task title", examples=["Implement login page"]
    )
    description: Optional[str] = Field(None, description="Detailed task description")
    status: str = Field("todo", description="Task status", examples=["todo", "in_progress", "review", "completed"])
    priority: str = Field("medium", description="Task priority level", examples=["low", "medium", "high", "critical"])
    story_points: Optional[int] = Field(None, description="Estimated story points", examples=[5])


class TaskCreate(TaskBase):
    """Schema for creating a new task."""

    project_id: int = Field(..., description="ID of the parent project")
    assigned_to: Optional[int] = Field(None, description="ID of the user assigned to the task")


class TaskResponse(TaskBase):
    """Schema for task data returned in API responses."""

    id: int = Field(..., description="Unique task identifier")
    project_id: int = Field(..., description="ID of the parent project")
    assigned_to: Optional[int] = Field(None, description="ID of the assigned user")
    created_by: int = Field(..., description="ID of the user who created the task")
    due_date: Optional[datetime] = Field(None, description="Task due date")
    completed_at: Optional[datetime] = Field(None, description="Task completion timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        from_attributes = True


class CommentBase(BaseModel):
    """Base schema for task comments."""

    content: str = Field(
        ..., min_length=1, description="Comment text content", examples=["Looks good, approved!"]
    )


class CommentCreate(CommentBase):
    """Schema for creating a new comment on a task."""

    task_id: int = Field(..., description="ID of the task to comment on")


class CommentResponse(CommentBase):
    """Schema for comment data returned in API responses."""

    id: int = Field(..., description="Unique comment identifier")
    task_id: int = Field(..., description="ID of the parent task")
    created_by: int = Field(..., description="ID of the comment author")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        from_attributes = True


class Token(BaseModel):
    """JWT token pair returned after successful authentication."""

    access_token: str = Field(..., description="JWT access token for API authorization")
    refresh_token: str = Field(..., description="JWT refresh token for obtaining new access tokens")
    token_type: str = Field("bearer", description="Token type (always 'bearer')")


class APIKeyCreate(BaseModel):
    """Schema for creating a new API key."""

    name: str = Field(
        ..., min_length=1, max_length=255, description="Human-readable API key name", examples=["CI/CD Pipeline"]
    )
    expires_at: Optional[datetime] = Field(None, description="Optional expiration date for the API key")


class APIKeyResponse(BaseModel):
    """Schema for API key data returned in API responses."""

    id: int = Field(..., description="Unique API key identifier")
    key: str = Field(..., description="The API key value (shown only on creation)")
    name: str = Field(..., description="Human-readable API key name")
    user_id: int = Field(..., description="ID of the key owner")
    expires_at: Optional[datetime] = Field(None, description="Expiration date")
    last_used_at: Optional[datetime] = Field(None, description="Last usage timestamp")
    is_active: bool = Field(..., description="Whether the API key is active")
    created_at: datetime = Field(..., description="Creation timestamp")

    class Config:
        from_attributes = True