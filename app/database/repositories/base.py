"""
Base repository for common database operations
"""
from typing import Generic, TypeVar, List, Optional, Type, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import DeclarativeBase

from app.database.models.base import BaseModel

T = TypeVar("T", bound=BaseModel)


class BaseRepository(Generic[T]):
    """
    Base repository with CRUD operations
    
    Provides common database operations for all models.
    """
    
    def __init__(self, model: Type[T], session: AsyncSession):
        """
        Initialize repository with model and session
        
        Args:
            model: SQLAlchemy model class
            session: Async database session
        """
        self.model = model
        self.session = session
    
    async def create(self, **kwargs: Any) -> T:
        """
        Create a new record
        
        Args:
            **kwargs: Model field values
            
        Returns:
            Created model instance
        """
        obj = self.model(**kwargs)
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj
    
    async def get_by_id(self, id: int) -> Optional[T]:
        """
        Get record by ID
        
        Args:
            id: Record ID
            
        Returns:
            Model instance or None if not found
        """
        stmt = select(self.model).where(self.model.id == id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_all(
        self,
        offset: int = 0,
        limit: int = 100,
        **filters: Any
    ) -> List[T]:
        """
        Get all records with optional filtering and pagination
        
        Args:
            offset: Number of records to skip
            limit: Maximum number of records to return
            **filters: Field filters
            
        Returns:
            List of model instances
        """
        stmt = select(self.model)
        
        # Apply filters
        for key, value in filters.items():
            if hasattr(self.model, key):
                stmt = stmt.where(getattr(self.model, key) == value)
        
        stmt = stmt.offset(offset).limit(limit)
        stmt = stmt.order_by(self.model.created_at.desc())
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def update(self, obj: T, **kwargs: Any) -> T:
        """
        Update a record
        
        Args:
            obj: Model instance to update
            **kwargs: Fields to update
            
        Returns:
            Updated model instance
        """
        for key, value in kwargs.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
        
        await self.session.flush()
        await self.session.refresh(obj)
        return obj
    
    async def update_by_id(self, id: int, **kwargs: Any) -> Optional[T]:
        """
        Update a record by ID
        
        Args:
            id: Record ID
            **kwargs: Fields to update
            
        Returns:
            Updated model instance or None if not found
        """
        stmt = (
            update(self.model)
            .where(self.model.id == id)
            .values(**kwargs)
            .returning(self.model)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def delete(self, obj: T) -> bool:
        """
        Delete a record
        
        Args:
            obj: Model instance to delete
            
        Returns:
            True if deleted successfully
        """
        await self.session.delete(obj)
        await self.session.flush()
        return True
    
    async def delete_by_id(self, id: int) -> bool:
        """
        Delete a record by ID
        
        Args:
            id: Record ID
            
        Returns:
            True if deleted, False if not found
        """
        stmt = delete(self.model).where(self.model.id == id)
        result = await self.session.execute(stmt)
        return result.rowcount > 0
    
    async def count(self, **filters: Any) -> int:
        """
        Count records matching filters
        
        Args:
            **filters: Field filters
            
        Returns:
            Number of matching records
        """
        from sqlalchemy import func
        
        stmt = select(func.count(self.model.id))
        
        for key, value in filters.items():
            if hasattr(self.model, key):
                stmt = stmt.where(getattr(self.model, key) == value)
        
        result = await self.session.execute(stmt)
        return result.scalar()
    
    async def exists(self, id: int) -> bool:
        """
        Check if a record exists by ID
        
        Args:
            id: Record ID
            
        Returns:
            True if record exists
        """
        stmt = select(self.model.id).where(self.model.id == id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None
