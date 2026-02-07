"""
File model
"""
from datetime import datetime
from typing import Optional, Any, Dict

from sqlalchemy import String, Integer, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSON

from app.database.models.base import BaseModel


class File(BaseModel):
    """
    File model for storing file metadata
    
    Attributes:
        id: Primary key
        user_id: Foreign key to users table
        filename: Storage filename
        original_filename: Original uploaded filename
        size: File size in bytes
        content_type: MIME type
        storage_path: Path in storage system
        metadata: File metadata (duration, resolution, codec, etc.) as JSON
        is_deleted: Soft delete flag
        deleted_at: Deletion timestamp
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """
    
    __tablename__ = "files"
    
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    size: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )
    content_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    storage_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )
    file_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
        default=lambda: {}
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )
    
    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="files"
    )
    
    # Indexes
    __table_args__ = (
        Index("ix_files_user_id", "user_id"),
        Index("ix_files_is_deleted", "is_deleted"),
        Index("ix_files_created_at", "created_at"),
        Index("ix_files_user_id_is_deleted", "user_id", "is_deleted"),
    )
    
    def __repr__(self) -> str:
        return f"<File(id={self.id}, user_id={self.user_id}, filename='{self.filename}')>"
