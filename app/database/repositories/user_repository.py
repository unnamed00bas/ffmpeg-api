"""
User repository for user-related database operations
"""
from typing import List, Optional, Any
import secrets
from passlib.context import CryptContext

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.repositories.base import BaseRepository
from app.database.models.user import User

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserRepository(BaseRepository[User]):
    """
    Repository for User model operations
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize UserRepository
        
        Args:
            session: Async database session
        """
        super().__init__(User, session)
    
    async def create(
        self,
        username: str,
        email: str,
        password: str,
        **kwargs: Any
    ) -> User:
        """
        Create a new user with hashed password
        
        Args:
            username: Username
            email: Email address
            password: Plain text password (will be hashed)
            **kwargs: Additional user fields
            
        Returns:
            Created user instance
        """
        hashed_password = self._hash_password(password)
        
        user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            **kwargs
        )
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email
        
        Args:
            email: Email address
            
        Returns:
            User instance or None if not found
        """
        stmt = select(User).where(User.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_by_username(self, username: str) -> Optional[User]:
        """
        Get user by username
        
        Args:
            username: Username
            
        Returns:
            User instance or None if not found
        """
        stmt = select(User).where(User.username == username)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_by_email_or_username(self, email_or_username: str) -> Optional[User]:
        """
        Get user by email or username
        
        Args:
            email_or_username: Email address or username
            
        Returns:
            User instance or None if not found
        """
        # Try email first
        user = await self.get_by_email(email_or_username)
        if user:
            return user
        # Try username
        return await self.get_by_username(email_or_username)
    
    async def get_by_api_key(self, api_key: str) -> Optional[User]:
        """
        Get user by API key
        
        Args:
            api_key: API key
            
        Returns:
            User instance or None if not found
        """
        stmt = select(User).where(User.api_key == api_key, User.is_active == True)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_users(
        self,
        offset: int = 0,
        limit: int = 100,
        active_only: bool = False
    ) -> List[User]:
        """
        Get list of users with pagination
        
        Args:
            offset: Number of users to skip
            limit: Maximum number of users to return
            active_only: Only return active users
            
        Returns:
            List of user instances
        """
        stmt = select(User)
        
        if active_only:
            stmt = stmt.where(User.is_active == True)
        
        stmt = stmt.offset(offset).limit(limit)
        stmt = stmt.order_by(User.created_at.desc())
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def authenticate(self, email: str, password: str) -> Optional[User]:
        """
        Authenticate user by email and password
        
        Args:
            email: Email address
            password: Plain text password
            
        Returns:
            User instance if authentication successful, None otherwise
        """
        user = await self.get_by_email(email)
        if not user or not user.is_active:
            return None
        
        if not self._verify_password(password, user.hashed_password):
            return None
        
        return user
    
    async def generate_api_key(self, user_id: int) -> str:
        """
        Generate and set new API key for user
        
        Args:
            user_id: User ID
            
        Returns:
            Generated API key
        """
        api_key = secrets.token_urlsafe(32)
        await self.update_by_id(user_id, api_key=api_key)
        return api_key
    
    async def revoke_api_key(self, user_id: int) -> bool:
        """
        Revoke user's API key
        
        Args:
            user_id: User ID
            
        Returns:
            True if revoked successfully
        """
        await self.update_by_id(user_id, api_key=None)
        return True
    
    async def change_password(
        self,
        user_id: int,
        old_password: str,
        new_password: str
    ) -> bool:
        """
        Change user password
        
        Args:
            user_id: User ID
            old_password: Current password
            new_password: New password
            
        Returns:
            True if password changed successfully
        """
        user = await self.get_by_id(user_id)
        if not user:
            return False
        
        if not self._verify_password(old_password, user.hashed_password):
            return False
        
        hashed_password = self._hash_password(new_password)
        await self.update_by_id(user_id, hashed_password=hashed_password)
        return True
    
    async def activate_user(self, user_id: int) -> bool:
        """
        Activate user account
        
        Args:
            user_id: User ID
            
        Returns:
            True if activated successfully
        """
        await self.update_by_id(user_id, is_active=True)
        return True
    
    async def deactivate_user(self, user_id: int) -> bool:
        """
        Deactivate user account
        
        Args:
            user_id: User ID
            
        Returns:
            True if deactivated successfully
        """
        await self.update_by_id(user_id, is_active=False)
        return True
    
    async def update_last_login(self, user_id: int) -> None:
        """
        Update user's last login timestamp
        
        Args:
            user_id: User ID
        """
        from datetime import datetime
        await self.update_by_id(user_id, updated_at=datetime.utcnow())
    
    def _hash_password(self, password: str) -> str:
        """
        Hash password using bcrypt
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password
        """
        # Truncate password to 72 bytes (bcrypt limitation)
        password_bytes = password.encode('utf-8')
        if len(password_bytes) > 72:
            password = password_bytes[:72].decode('utf-8', errors='ignore')
        return pwd_context.hash(password)
    
    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify password against hashed password
        
        Args:
            plain_password: Plain text password
            hashed_password: Hashed password
            
        Returns:
            True if password matches
        """
        return pwd_context.verify(plain_password, hashed_password)
