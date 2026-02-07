"""
Схемы для пользовательских endpoints: /users/me, settings, stats, history.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from app.schemas.task import TaskResponse


class UserResponse(BaseModel):
    """Профиль текущего пользователя (без пароля)."""
    id: int
    username: str
    email: str
    is_admin: bool = False
    is_active: bool = True
    settings: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserSettings(BaseModel):
    """Настройки пользователя."""
    settings: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class UserStats(BaseModel):
    """Статистика пользователя: задачи и хранилище."""
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    processing_tasks: int
    total_files: int
    storage_used: int
    storage_limit: int


class UserHistory(BaseModel):
    """История задач с пагинацией."""
    tasks: List[TaskResponse]
    total: int
    page: int
    page_size: int
