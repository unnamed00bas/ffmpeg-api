"""Authentication endpoints"""
from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.database.models.user import User
from app.database.repositories.user_repository import UserRepository
from app.auth.dependencies import (
    get_current_user,
    get_current_active_user,
    get_db,
    jwt_service,
    security_service
)
from app.config import settings


# Pydantic models for request/response
class UserRegister(BaseModel):
    """User registration request"""
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., min_length=8, description="Password")

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format"""
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username can only contain letters, numbers, underscores and hyphens')
        return v


class UserLogin(BaseModel):
    """User login request"""
    email_or_username: str = Field(..., description="Email or username")
    password: str = Field(..., description="Password")


class UserResponse(BaseModel):
    """User response model"""
    id: int
    username: str
    email: str
    settings: Optional[dict] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    """Token response model"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # in seconds


class RefreshTokenRequest(BaseModel):
    """Refresh token request"""
    refresh_token: str = Field(..., description="Refresh token")


# Create router
router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED, tags=["Authentication"])
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user

    - **username**: 3-50 characters, letters, numbers, underscores, hyphens
    - **email**: Valid email address
    - **password**: At least 8 characters, must contain uppercase, lowercase, and digit
    """
    user_repo = UserRepository(db)

    # Check if email already exists
    existing_email = await user_repo.get_by_email(user_data.email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Check if username already exists
    existing_username = await user_repo.get_by_username(user_data.username)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )

    # Validate password strength
    try:
        security_service.validate_password_strength(user_data.password)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    # Create user (password will be hashed by repository)
    user = await user_repo.create(
        username=user_data.username,
        email=user_data.email,
        password=user_data.password
    )
    await db.commit()

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        settings=user.settings,
        created_at=user.created_at.isoformat() if user.created_at else None
    )


@router.post("/login", response_model=Token, tags=["Authentication"])
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticate user and return tokens

    Uses OAuth2 password flow
    """
    user_repo = UserRepository(db)

    # Get user by email or username
    user = await user_repo.get_by_email_or_username(form_data.username)

    # Verify password
    if not user or not security_service.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email/username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    # Update last login
    await user_repo.update_last_login(user.id)
    await db.commit()

    # Create access token
    access_token = jwt_service.create_access_token(
        user_id=user.id,
        expires_delta=timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    # Create refresh token
    refresh_token = jwt_service.create_refresh_token(
        user_id=user.id,
        expires_delta=timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    )

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/refresh", response_model=Token, tags=["Authentication"])
async def refresh(
    refresh_request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token using refresh token

    Returns new access token and the same refresh token
    """
    try:
        # Verify refresh token
        user_id = jwt_service.get_user_id_from_token(refresh_request.refresh_token)

        # Check if it's actually a refresh token
        if not jwt_service.is_refresh_token(refresh_request.refresh_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )

        # Verify user exists
        user_repo = UserRepository(db)
        user = await user_repo.get_by_id(user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive"
            )

        # Create new access token
        access_token = jwt_service.create_access_token(
            user_id=user.id,
            expires_delta=timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        )

        return Token(
            access_token=access_token,
            refresh_token=refresh_request.refresh_token,  # Return the same refresh token
            token_type="bearer",
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )


@router.get("/me", response_model=UserResponse, tags=["Authentication"])
async def get_me(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user information

    Requires valid access token
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Executing get_me for user: {current_user.id}")
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        settings=current_user.settings,
        created_at=current_user.created_at.isoformat() if current_user.created_at else None
    )
