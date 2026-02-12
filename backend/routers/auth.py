from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
from typing import Optional
import secrets

from ..database import get_db
from ..models import User, APIKey
from ..schemas import UserCreate, UserResponse, Token, APIKeyCreate, APIKeyResponse
from ..security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token
)

router = APIRouter(tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    responses={400: {"description": "Email or username already registered"}},
)
async def register_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user account.

    Creates a new user with the provided username, email, and password.
    The username and email must be unique across the platform.
    """
    # Check if user exists
    result = await db.execute(
        select(User).where(
            (User.email == user_data.email) | (User.username == user_data.username)
        )
    )
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password,
        full_name=user_data.full_name
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return new_user

@router.post(
    "/login",
    response_model=Token,
    summary="Login and obtain tokens",
    responses={
        401: {"description": "Incorrect username or password"},
        400: {"description": "Inactive user account"},
    },
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """Authenticate a user and return JWT tokens.

    Accepts username and password via OAuth2 form data.
    Returns an access token and a refresh token on success.
    """
    # Find user
    result = await db.execute(
        select(User).where(User.username == form_data.username)
    )
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    # Create tokens
    access_token = create_access_token(data={"sub": user.username})
    refresh_token = create_refresh_token(data={"sub": user.username})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
    responses={401: {"description": "Invalid or expired token"}},
)
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve the profile of the currently authenticated user.

    Requires a valid Bearer token in the Authorization header.
    """
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    username: str = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
    
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    return user

@router.post(
    "/api-keys",
    response_model=APIKeyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new API key",
    responses={401: {"description": "Not authenticated"}},
)
async def create_api_key(
    api_key_data: APIKeyCreate,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """Create a new API key for the authenticated user.

    API keys can be used as an alternative to JWT tokens for API access.
    An optional expiration date may be provided.
    """
    # Get current user
    user = await get_current_user(token, db)
    
    # Generate secure API key
    key = f"ep_{secrets.token_urlsafe(32)}"
    
    # Create API key
    new_api_key = APIKey(
        key=key,
        name=api_key_data.name,
        user_id=user.id,
        expires_at=api_key_data.expires_at
    )
    
    db.add(new_api_key)
    await db.commit()
    await db.refresh(new_api_key)
    
    return new_api_key

@router.get(
    "/api-keys",
    response_model=list[APIKeyResponse],
    summary="List API keys",
    responses={401: {"description": "Not authenticated"}},
)
async def list_api_keys(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    """List all API keys belonging to the authenticated user."""
    user = await get_current_user(token, db)
    
    result = await db.execute(
        select(APIKey).where(APIKey.user_id == user.id)
    )
    api_keys = result.scalars().all()
    
    return api_keys