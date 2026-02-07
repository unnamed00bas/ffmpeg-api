"""
Схемы ответов для admin API.
"""
from datetime import datetime
from typing import List

from pydantic import BaseModel

from app.schemas.task import TaskResponse


class AdminTasksResponse(BaseModel):
    """Список задач (админ)."""
    tasks: List[TaskResponse]
    total: int
    page: int
    page_size: int


class AdminUserStats(BaseModel):
    """Пользователь с счётчиком задач для админки."""
    id: int
    username: str
    email: str
    is_admin: bool
    is_active: bool
    created_at: datetime
    tasks_count: int


class AdminUsersResponse(BaseModel):
    """Список пользователей (админ)."""
    users: List[AdminUserStats]
    total: int
    page: int
    page_size: int


class AdminMetricsResponse(BaseModel):
    """Системные метрики для админки."""
    total_users: int
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    processing_tasks: int
    total_files: int
    total_storage: int
    queue_size: int
    active_workers: int


class AdminQueueStatusResponse(BaseModel):
    """Статус очереди Celery."""
    pending: int
    processing: int
    reserved: int
    total: int
    workers: List[str]
