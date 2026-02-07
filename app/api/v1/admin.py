"""
Admin API: задачи, пользователи, метрики, очередь, ручная очистка.
"""
import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_admin_user, get_db
from app.database.models.user import User
from app.database.repositories.file_repository import FileRepository
from app.database.repositories.task_repository import TaskRepository
from app.database.repositories.user_repository import UserRepository
from app.database.models.task import TaskStatus
from app.schemas.admin import (
    AdminMetricsResponse,
    AdminQueueStatusResponse,
    AdminTasksResponse,
    AdminUserStats,
    AdminUsersResponse,
)
from app.schemas.task import TaskResponse

router = APIRouter()


@router.get("/tasks", response_model=AdminTasksResponse)
async def get_all_tasks(
    status: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Список всех задач с фильтрами (только для админов)."""
    task_repo = TaskRepository(db)
    status_enum = None
    if status is not None:
        try:
            status_enum = TaskStatus(status)
        except ValueError:
            from fastapi import HTTPException
            raise HTTPException(status_code=422, detail="Invalid status")
    result = await task_repo.get_all_tasks(
        status=status_enum,
        user_id=user_id,
        offset=offset,
        limit=limit,
    )
    return AdminTasksResponse(
        tasks=[TaskResponse.model_validate(t) for t in result.tasks],
        total=result.total,
        page=offset // limit + 1 if limit else 1,
        page_size=limit,
    )


@router.get("/users", response_model=AdminUsersResponse)
async def get_all_users(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Список пользователей со счётчиком задач (только для админов)."""
    user_repo = UserRepository(db)
    task_repo = TaskRepository(db)
    users = await user_repo.get_users(offset=offset, limit=limit)
    total = await user_repo.count()
    users_with_stats = []
    for u in users:
        stats = await task_repo.get_tasks_statistics(u.id)
        users_with_stats.append(
            AdminUserStats(
                id=u.id,
                username=u.username,
                email=u.email,
                is_admin=u.is_admin,
                is_active=u.is_active,
                created_at=u.created_at,
                tasks_count=stats.get("total", 0),
            )
        )
    return AdminUsersResponse(
        users=users_with_stats,
        total=total,
        page=offset // limit + 1 if limit else 1,
        page_size=limit,
    )


@router.get("/metrics", response_model=AdminMetricsResponse)
async def get_system_metrics(
    current_admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Системные метрики: пользователи, задачи, файлы, очередь (только для админов)."""
    task_repo = TaskRepository(db)
    file_repo = FileRepository(db)
    user_repo = UserRepository(db)
    all_stats = await task_repo.get_all_tasks_statistics()
    by_status = all_stats.get("by_status") or {}
    total_storage = await file_repo.get_total_storage_usage()
    total_files = await file_repo.count_all()
    total_users = await user_repo.count()
    # Celery inspect (sync)
    from app.queue.celery_app import celery_app
    inspect = celery_app.control.inspect()
    active = inspect.active() or {}
    queue_size = sum(len(tasks) for tasks in active.values())
    return AdminMetricsResponse(
        total_users=total_users,
        total_tasks=all_stats.get("total", 0),
        completed_tasks=by_status.get("completed", 0),
        failed_tasks=by_status.get("failed", 0),
        processing_tasks=by_status.get("processing", 0),
        total_files=total_files,
        total_storage=total_storage,
        queue_size=queue_size,
        active_workers=len(active),
    )


@router.get("/queue-status", response_model=AdminQueueStatusResponse)
async def get_queue_status(
    current_admin: User = Depends(get_current_admin_user),
):
    """Статус очереди Celery (только для админов)."""
    from app.queue.celery_app import celery_app
    inspect = celery_app.control.inspect()
    active = inspect.active() or {}
    scheduled = inspect.scheduled() or {}
    reserved = inspect.reserved() or {}
    pending_count = sum(len(t) for t in scheduled.values())
    processing_count = sum(len(t) for t in active.values())
    reserved_count = sum(len(t) for t in reserved.values())
    return AdminQueueStatusResponse(
        pending=pending_count,
        processing=processing_count,
        reserved=reserved_count,
        total=pending_count + processing_count + reserved_count,
        workers=list(active.keys()),
    )


@router.post("/cleanup")
async def manual_cleanup(
    file_retention_days: Optional[int] = Query(None, ge=1, le=90),
    task_retention_days: Optional[int] = Query(None, ge=1, le=365),
    current_admin: User = Depends(get_current_admin_user),
):
    """Ручной запуск очистки старых файлов и задач (только для админов)."""
    from app.queue.periodic_tasks import (
        _async_cleanup_old_files,
        _async_cleanup_temp_files,
        _async_cleanup_old_tasks,
    )
    from app.config import get_settings
    results: dict = {}
    if file_retention_days is not None:
        deleted = await _async_cleanup_old_files(file_retention_days)
        results["files"] = f"Deleted {deleted} old files"
    deleted_temp = await _async_cleanup_temp_files()
    results["temp_files"] = f"Deleted {deleted_temp} temp files"
    if task_retention_days is not None:
        deleted_tasks = await _async_cleanup_old_tasks(task_retention_days)
        results["tasks"] = f"Deleted {deleted_tasks} old tasks"
    return results
