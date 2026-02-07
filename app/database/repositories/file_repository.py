"""
File repository for file-related database operations
"""
from typing import List, Optional, Any, Dict
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.database.repositories.base import BaseRepository
from app.database.models.file import File


class FileRepository(BaseRepository[File]):
    """
    Repository for File model operations
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize FileRepository
        
        Args:
            session: Async database session
        """
        super().__init__(File, session)
    
    async def create(
        self,
        user_id: int,
        filename: str,
        original_filename: str,
        size: int,
        content_type: str,
        storage_path: str,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any
    ) -> File:
        """
        Create a new file record
        
        Args:
            user_id: User ID
            filename: Storage filename
            original_filename: Original uploaded filename
            size: File size in bytes
            content_type: MIME type
            storage_path: Path in storage system
            metadata: File metadata (duration, resolution, codec, etc.)
            **kwargs: Additional file fields
            
        Returns:
            Created file instance
        """
        file = File(
            user_id=user_id,
            filename=filename,
            original_filename=original_filename,
            size=size,
            content_type=content_type,
            storage_path=storage_path,
            file_metadata=metadata or {},
            **kwargs
        )
        self.session.add(file)
        await self.session.flush()
        await self.session.refresh(file)
        return file
    
    async def get_by_user(
        self,
        user_id: int,
        offset: int = 0,
        limit: int = 100,
        include_deleted: bool = False
    ) -> List[File]:
        """
        Get files for a specific user with pagination
        
        Args:
            user_id: User ID
            offset: Number of files to skip
            limit: Maximum number of files to return
            include_deleted: Include soft-deleted files
            
        Returns:
            List of file instances
        """
        stmt = select(File).where(File.user_id == user_id)
        
        if not include_deleted:
            stmt = stmt.where(File.is_deleted == False)
        
        stmt = stmt.offset(offset).limit(limit)
        stmt = stmt.order_by(File.created_at.desc())
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_by_storage_path(self, storage_path: str) -> Optional[File]:
        """
        Get file by storage path
        
        Args:
            storage_path: Storage path
            
        Returns:
            File instance or None if not found
        """
        stmt = select(File).where(File.storage_path == storage_path)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_by_content_type(
        self,
        user_id: int,
        content_type: str,
        offset: int = 0,
        limit: int = 100
    ) -> List[File]:
        """
        Get files by content type for a user
        
        Args:
            user_id: User ID
            content_type: MIME type
            offset: Number of files to skip
            limit: Maximum number of files to return
            
        Returns:
            List of file instances
        """
        stmt = select(File).where(
            and_(
                File.user_id == user_id,
                File.content_type == content_type,
                File.is_deleted == False
            )
        )
        stmt = stmt.offset(offset).limit(limit)
        stmt = stmt.order_by(File.created_at.desc())
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def mark_as_deleted(self, file_id: int) -> bool:
        """
        Soft delete a file by ID
        
        Args:
            file_id: File ID
            
        Returns:
            True if marked as deleted
        """
        file = await self.get_by_id(file_id)
        if file and not file.is_deleted:
            await self.update(
                file,
                is_deleted=True,
                deleted_at=datetime.utcnow()
            )
            return True
        return False
    
    async def mark_as_deleted_by_storage_path(self, storage_path: str) -> bool:
        """
        Soft delete a file by storage path
        
        Args:
            storage_path: Storage path
            
        Returns:
            True if marked as deleted
        """
        file = await self.get_by_storage_path(storage_path)
        if file and not file.is_deleted:
            await self.update(
                file,
                is_deleted=True,
                deleted_at=datetime.utcnow()
            )
            return True
        return False
    
    async def restore(self, file_id: int) -> bool:
        """
        Restore a soft-deleted file
        
        Args:
            file_id: File ID
            
        Returns:
            True if restored successfully
        """
        file = await self.get_by_id(file_id)
        if file and file.is_deleted:
            await self.update(
                file,
                is_deleted=False,
                deleted_at=None
            )
            return True
        return False
    
    async def get_user_storage_usage(self, user_id: int) -> int:
        """
        Get total storage usage for a user
        
        Args:
            user_id: User ID
            
        Returns:
            Total storage usage in bytes
        """
        stmt = select(func.sum(File.size)).where(
            and_(
                File.user_id == user_id,
                File.is_deleted == False
            )
        )
        
        result = await self.session.execute(stmt)
        return result.scalar() or 0
    
    async def get_user_file_count(self, user_id: int, include_deleted: bool = False) -> int:
        """
        Get total file count for a user
        
        Args:
            user_id: User ID
            include_deleted: Include soft-deleted files
            
        Returns:
            Number of files
        """
        stmt = select(func.count(File.id)).where(File.user_id == user_id)
        
        if not include_deleted:
            stmt = stmt.where(File.is_deleted == False)
        
        result = await self.session.execute(stmt)
        return result.scalar() or 0
    
    async def get_files_by_size_range(
        self,
        user_id: int,
        min_size: int,
        max_size: int,
        offset: int = 0,
        limit: int = 100
    ) -> List[File]:
        """
        Get files within a size range for a user
        
        Args:
            user_id: User ID
            min_size: Minimum file size in bytes
            max_size: Maximum file size in bytes
            offset: Number of files to skip
            limit: Maximum number of files to return
            
        Returns:
            List of file instances
        """
        stmt = select(File).where(
            and_(
                File.user_id == user_id,
                File.size >= min_size,
                File.size <= max_size,
                File.is_deleted == False
            )
        )
        stmt = stmt.offset(offset).limit(limit)
        stmt = stmt.order_by(File.size.desc())
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_files_by_date_range(
        self,
        user_id: int,
        start_date: datetime,
        end_date: datetime,
        offset: int = 0,
        limit: int = 100
    ) -> List[File]:
        """
        Get files within a date range for a user
        
        Args:
            user_id: User ID
            start_date: Start of date range
            end_date: End of date range
            offset: Number of files to skip
            limit: Maximum number of files to return
            
        Returns:
            List of file instances
        """
        stmt = select(File).where(
            and_(
                File.user_id == user_id,
                File.created_at >= start_date,
                File.created_at <= end_date,
                File.is_deleted == False
            )
        )
        stmt = stmt.offset(offset).limit(limit)
        stmt = stmt.order_by(File.created_at.desc())
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_large_files(
        self,
        user_id: int,
        min_size_mb: int = 100,
        limit: int = 100
    ) -> List[File]:
        """
        Get large files for a user
        
        Args:
            user_id: User ID
            min_size_mb: Minimum file size in MB
            limit: Maximum number of files to return
            
        Returns:
            List of file instances sorted by size descending
        """
        min_size_bytes = min_size_mb * 1024 * 1024
        
        stmt = select(File).where(
            and_(
                File.user_id == user_id,
                File.size >= min_size_bytes,
                File.is_deleted == False
            )
        )
        stmt = stmt.order_by(File.size.desc())
        stmt = stmt.limit(limit)
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_recent_files(
        self,
        user_id: int,
        days: int = 7,
        limit: int = 100
    ) -> List[File]:
        """
        Get recent files for a user
        
        Args:
            user_id: User ID
            days: Number of days to look back
            limit: Maximum number of files to return
            
        Returns:
            List of file instances sorted by creation date descending
        """
        from datetime import timedelta
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        stmt = select(File).where(
            and_(
                File.user_id == user_id,
                File.created_at >= start_date,
                File.is_deleted == False
            )
        )
        stmt = stmt.order_by(File.created_at.desc())
        stmt = stmt.limit(limit)
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def delete_permanently(self, file_id: int) -> bool:
        """
        Permanently delete a file record
        
        Args:
            file_id: File ID
            
        Returns:
            True if deleted successfully
        """
        return await self.delete_by_id(file_id)
    
    async def get_files_older_than(self, cutoff_date: datetime) -> List[File]:
        """
        Файлы, созданные раньше указанной даты (для автоочистки).
        """
        stmt = select(File).where(
            and_(
                File.created_at < cutoff_date,
                File.is_deleted == False,
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_total_storage_usage(self) -> int:
        """Суммарный размер всех неудалённых файлов."""
        stmt = select(func.sum(File.size)).where(File.is_deleted == False)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def count_all(self, include_deleted: bool = False) -> int:
        """Общее количество файлов."""
        stmt = select(func.count(File.id))
        if not include_deleted:
            stmt = stmt.where(File.is_deleted == False)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_files_statistics(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get files statistics
        
        Args:
            user_id: Optional user ID to filter stats
            
        Returns:
            Dictionary with statistics
        """
        stmt = select(File)
        
        if user_id:
            stmt = stmt.where(File.user_id == user_id)
        
        stmt = stmt.where(File.is_deleted == False)
        
        result = await self.session.execute(stmt)
        files = result.scalars().all()
        
        stats: Dict[str, Any] = {
            "total_count": len(files),
            "total_size_bytes": sum(f.size for f in files),
            "average_size_bytes": 0.0,
            "by_content_type": {}
        }
        
        if files:
            stats["average_size_bytes"] = stats["total_size_bytes"] / len(files)
        
        # Count by content type
        for file in files:
            content_type = file.content_type
            stats["by_content_type"][content_type] = (
                stats["by_content_type"].get(content_type, 0) + 1
            )
        
        return stats
    
    async def update_metadata(
        self,
        file_id: int,
        metadata: Dict[str, Any]
    ) -> Optional[File]:
        """
        Update file metadata
        
        Args:
            file_id: File ID
            metadata: New metadata
            
        Returns:
            Updated file instance or None if not found
        """
        return await self.update_by_id(file_id, file_metadata=metadata)
