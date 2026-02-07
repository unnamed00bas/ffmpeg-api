"""
Task model
"""
from datetime import datetime
from typing import Optional, Any, Dict
from enum import Enum

from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSON, ENUM

from app.database.models.base import BaseModel


class TaskType(str, Enum):
    """Task types enumeration"""
    JOIN = "join"
    AUDIO_OVERLAY = "audio_overlay"
    TEXT_OVERLAY = "text_overlay"
    SUBTITLES = "subtitles"
    VIDEO_OVERLAY = "video_overlay"
    COMBINED = "combined"


class TaskStatus(str, Enum):
    """Task status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(BaseModel):
    """
    Task model for video processing operations
    
    Attributes:
        id: Primary key
        user_id: Foreign key to users table
        type: Type of task (join, audio_overlay, etc.)
        status: Current status (pending, processing, completed, etc.)
        input_files: List of input file IDs (JSON)
        output_files: List of output file IDs (JSON)
        config: Task configuration (JSON)
        error_message: Error message if failed
        progress: Progress percentage (0.0-100.0)
        result: Task result (JSON)
        retry_count: Number of retries
        created_at: Creation timestamp
        updated_at: Last update timestamp
        completed_at: Completion timestamp
    """
    
    __tablename__ = "tasks"
    
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    type: Mapped[TaskType] = mapped_column(
        ENUM(TaskType, name="task_type", create_type=True),
        nullable=False
    )
    status: Mapped[TaskStatus] = mapped_column(
        ENUM(TaskStatus, name="task_status", create_type=True),
        default=TaskStatus.PENDING,
        nullable=False
    )
    input_files: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: []
    )
    output_files: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: []
    )
    config: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        String(2000),
        nullable=True
    )
    progress: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False
    )
    result: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )
    
    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="tasks"
    )
    operation_logs: Mapped[list["OperationLog"]] = relationship(
        "OperationLog",
        back_populates="task",
        cascade="all, delete-orphan"
    )
    
    # Indexes
    __table_args__ = (
        Index("ix_tasks_user_id_status", "user_id", "status"),
        Index("ix_tasks_status", "status"),
        Index("ix_tasks_created_at", "created_at"),
        Index("ix_tasks_type", "type"),
    )
    
    def __repr__(self) -> str:
        return f"<Task(id={self.id}, user_id={self.user_id}, type='{self.type}', status='{self.status}')>"
