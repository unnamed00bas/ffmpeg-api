"""
Task Pydantic schemas for API request/response
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.database.models.task import TaskType, TaskStatus


class TaskCreate(BaseModel):
    """Схема создания задачи"""

    type: TaskType
    config: Dict[str, Any]
    priority: int = Field(default=5, ge=1, le=10)


class TaskUpdate(BaseModel):
    """Схема обновления задачи (внутренняя)"""

    status: Optional[TaskStatus] = None
    progress: Optional[float] = Field(None, ge=0, le=100)
    error_message: Optional[str] = None


class TaskResponse(BaseModel):
    """Схема ответа с задачей"""

    id: int
    user_id: int
    type: TaskType
    status: TaskStatus
    input_files: List[int]
    output_files: List[int]
    config: Dict[str, Any]
    error_message: Optional[str] = None
    progress: float
    result: Optional[Dict[str, Any]] = None
    retry_count: int
    priority: int
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    """Схема списка задач с пагинацией"""

    tasks: List[TaskResponse]
    total: int
    page: int
    page_size: int
