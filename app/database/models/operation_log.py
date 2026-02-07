"""
Operation Log model
"""
from datetime import datetime
from typing import Optional, Any, Dict

from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSON

from app.database.models.base import BaseModel


class OperationLog(BaseModel):
    """
    Operation Log model for tracking task operations
    
    Attributes:
        id: Primary key
        task_id: Foreign key to tasks table
        operation_type: Type of operation (e.g., "encode", "merge", "extract")
        duration: Operation duration in seconds
        success: Whether operation was successful
        error_details: Error details (JSON) if operation failed
        timestamp: Operation timestamp
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """
    
    __tablename__ = "operation_logs"
    
    task_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tasks.id", ondelete="CASCADE"),
        index=True,
        nullable=False
    )
    operation_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    duration: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    success: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False
    )
    error_details: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        server_default="CURRENT_TIMESTAMP",
        nullable=False,
        index=True
    )
    
    # Relationships
    task: Mapped["Task"] = relationship(
        "Task",
        back_populates="operation_logs"
    )
    
    # Indexes
    __table_args__ = (
        Index("ix_operation_logs_task_id", "task_id"),
        Index("ix_operation_logs_operation_type", "operation_type"),
        Index("ix_operation_logs_timestamp", "timestamp"),
        Index("ix_operation_logs_task_id_timestamp", "task_id", "timestamp"),
    )
    
    def __repr__(self) -> str:
        return f"<OperationLog(id={self.id}, task_id={self.task_id}, operation_type='{self.operation_type}')>"
