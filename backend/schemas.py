from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime
from typing import Optional, List

class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    email: EmailStr
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class UserResponse(UserBase):
    id: int
    is_active: bool
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class UserProfileBase(BaseModel):
    phone_number: Optional[str] = Field(None, max_length=20)
    location: Optional[str] = Field(None, max_length=255)
    job_title: Optional[str] = Field(None, max_length=255)
    department: Optional[str] = Field(None, max_length=255)
    timezone: str = Field('UTC', max_length=50)
    language: str = Field('en', max_length=10)
    linkedin_url: Optional[str] = Field(None, max_length=500)
    github_url: Optional[str] = Field(None, max_length=500)
    twitter_url: Optional[str] = Field(None, max_length=500)
    website: Optional[str] = Field(None, max_length=500)
    date_of_birth: Optional[datetime] = None
    profile_visibility: str = Field('public', max_length=20)
    notification_preferences: Optional[dict] = None

    @field_validator('profile_visibility')
    @classmethod
    def validate_visibility(cls, v: str) -> str:
        allowed = ('public', 'private', 'organization')
        if v not in allowed:
            msg = f"profile_visibility must be one of {allowed}"
            raise ValueError(msg)
        return v

class UserProfileCreate(UserProfileBase):
    pass

class UserProfileUpdate(UserProfileBase):
    pass

class UserProfileResponse(UserProfileBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class OrganizationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    website: Optional[str] = None

class OrganizationCreate(OrganizationBase):
    pass

class OrganizationResponse(OrganizationBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    status: str = 'active'
    priority: str = 'medium'
    budget: Optional[float] = None

class ProjectCreate(ProjectBase):
    organization_id: int

class ProjectResponse(ProjectBase):
    id: int
    organization_id: int
    created_by: int
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    status: str = 'todo'
    priority: str = 'medium'
    story_points: Optional[int] = None

class TaskCreate(TaskBase):
    project_id: int
    assigned_to: Optional[int] = None

class TaskResponse(TaskBase):
    id: int
    project_id: int
    assigned_to: Optional[int] = None
    created_by: int
    due_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class CommentBase(BaseModel):
    content: str = Field(..., min_length=1)

class CommentCreate(CommentBase):
    task_id: int

class CommentResponse(CommentBase):
    id: int
    task_id: int
    created_by: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = 'bearer'

class APIKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    expires_at: Optional[datetime] = None

class APIKeyResponse(BaseModel):
    id: int
    key: str
    name: str
    user_id: int
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True