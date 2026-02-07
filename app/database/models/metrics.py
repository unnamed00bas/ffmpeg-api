"""
Metrics model
"""
from typing import Optional, Any, Dict

from sqlalchemy import String, Float, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSON

from app.database.models.base import BaseModel


class Metrics(BaseModel):
    """
    Metrics model for storing application metrics
    
    Attributes:
        id: Primary key
        metric_name: Name of the metric (e.g., "task_duration", "queue_size")
        metric_value: Value of the metric
        tags: Additional tags/metadata (JSON)
        timestamp: Metric timestamp
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """
    
    __tablename__ = "metrics"
    
    metric_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True
    )
    metric_value: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )
    tags: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        default=lambda: {}
    )
    timestamp: Mapped[DateTime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
        server_default="CURRENT_TIMESTAMP"
    )
    
    # Indexes
    __table_args__ = (
        Index("ix_metrics_metric_name_timestamp", "metric_name", "timestamp"),
        Index("ix_metrics_metric_name", "metric_name"),
        Index("ix_metrics_timestamp", "timestamp"),
    )
    
    def __repr__(self) -> str:
        return f"<Metrics(id={self.id}, metric_name='{self.metric_name}', metric_value={self.metric_value})>"
