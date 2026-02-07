"""
Users API: /me, settings, stats, history
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_active_user, get_db
from app.database.models.task import TaskStatus, TaskType
from app.database.models.user import User
from app.database.repositories.file_repository import FileRepository
from app.database.repositories.task_repository import TaskRepository
from app.database.repositories.user_repository import UserRepository
from pydantic import BaseModel as PydanticBase

from app.schemas.task import TaskResponse
from app.schemas.user import UserHistory, UserResponse, UserSettings, UserStats

router = APIRouter()


class UserSettingsUpdate(PydanticBase):
    """Тело запроса обновления настроек (произвольные ключи)."""
    class Config:
        extra = "allow"


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
):
    """Информация о текущем пользователе."""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        is_admin=current_user.is_admin,
        is_active=current_user.is_active,
        settings=current_user.settings,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
    )


@router.get("/me/settings", response_model=UserSettings)
async def get_user_settings(
    current_user: User = Depends(get_current_active_user),
):
    """Настройки пользователя."""
    return UserSettings(
        settings=current_user.settings or {},
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
    )


@router.put("/me/settings", response_model=UserSettings)
async def update_user_settings(
    body: UserSettingsUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Обновление настроек (слияние с существующими)."""
    user_repo = UserRepository(db)
    current = current_user.settings or {}
    updated = {**current, **body.model_dump(exclude_unset=True)}
    await user_repo.update_by_id(current_user.id, settings=updated)
    await db.commit()
    updated_user = await user_repo.get_by_id(current_user.id)
    if not updated_user:
        return UserSettings(settings=updated, created_at=current_user.created_at, updated_at=current_user.updated_at)
    return UserSettings(
        settings=updated_user.settings or {},
        created_at=updated_user.created_at,
        updated_at=updated_user.updated_at,
    )


@router.get("/me/stats", response_model=UserStats)
async def get_user_stats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Статистика: задачи и хранилище."""
    task_repo = TaskRepository(db)
    file_repo = FileRepository(db)
    tasks_stats = await task_repo.get_tasks_statistics(current_user.id)
    by_status = tasks_stats.get("by_status") or {}
    storage_used = await file_repo.get_user_storage_usage(current_user.id)
    files_count = await file_repo.get_user_file_count(current_user.id)
    return UserStats(
        total_tasks=tasks_stats.get("total", 0),
        completed_tasks=by_status.get("completed", 0),
        failed_tasks=by_status.get("failed", 0),
        processing_tasks=by_status.get("processing", 0),
        total_files=files_count,
        storage_used=storage_used,
        storage_limit=1073741824,  # 1GB
    )


@router.get("/me/history", response_model=UserHistory)
async def get_user_history(
    status: Optional[str] = Query(None),
    task_type: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """История задач с пагинацией и фильтрами."""
    filters: dict = {}
    if status is not None:
        try:
            filters["status"] = TaskStatus(status)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid status")
    if task_type is not None:
        try:
            filters["type"] = TaskType(task_type)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid task_type")
    task_repo = TaskRepository(db)
    tasks = await task_repo.get_by_user(
        current_user.id,
        offset=offset,
        limit=limit,
        filters=filters or None,
    )
    total = await task_repo.count_by_user(current_user.id, filters=filters or None)
    return UserHistory(
        tasks=[TaskResponse.model_validate(t) for t in tasks],
        total=total,
        page=offset // limit + 1 if limit else 1,
        page_size=limit,
    )
