"""
Task business logic service
"""
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.task import Task, TaskStatus, TaskType
from app.database.repositories.task_repository import TaskRepository
from app.schemas.task import TaskListResponse, TaskResponse


class TaskService:
    """Сервис управления задачами."""

    def __init__(self, session: AsyncSession):
        self._session = session
        self._repo = TaskRepository(session)

    @staticmethod
    def _task_to_response(task: Task) -> TaskResponse:
        """Преобразование модели Task в TaskResponse."""
        input_files = task.input_files if isinstance(task.input_files, list) else []
        output_files = task.output_files if isinstance(task.output_files, list) else []
        return TaskResponse(
            id=task.id,
            user_id=task.user_id,
            type=task.type,
            status=task.status,
            input_files=input_files,
            output_files=output_files,
            config=task.config or {},
            error_message=task.error_message,
            progress=task.progress,
            result=task.result,
            retry_count=task.retry_count,
            priority=getattr(task, "priority", 5),
            created_at=task.created_at,
            updated_at=task.updated_at,
            completed_at=task.completed_at,
        )

    async def create_task(
        self,
        user_id: int,
        task_type: TaskType,
        config: Dict[str, Any],
        input_files: Optional[List[int]] = None,
        output_files: Optional[List[int]] = None,
        priority: int = 5,
    ) -> Task:
        """Создание задачи в БД."""
        task = await self._repo.create(
            user_id=user_id,
            task_type=task_type,
            config=config,
            input_files=input_files or [],
            output_files=output_files or [],
            priority=priority,
        )
        await self._session.commit()
        await self._session.refresh(task)
        return task

    async def get_task(self, task_id: int, user_id: int) -> Optional[Task]:
        """Получение задачи по ID с проверкой владельца."""
        return await self._repo.get_by_id_and_user(task_id, user_id)

    async def get_tasks(
        self,
        user_id: int,
        status: Optional[TaskStatus] = None,
        task_type: Optional[TaskType] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> TaskListResponse:
        """Список задач пользователя с фильтрами и пагинацией."""
        filters: Dict[str, Any] = {}
        if status is not None:
            filters["status"] = status
        if task_type is not None:
            filters["type"] = task_type

        tasks = await self._repo.get_by_user(
            user_id=user_id,
            offset=offset,
            limit=limit,
            filters=filters or None,
        )
        total = await self._repo.count_by_user(user_id, filters=filters or None)

        return TaskListResponse(
            tasks=[self._task_to_response(t) for t in tasks],
            total=total,
            page=offset // limit + 1 if limit else 1,
            page_size=limit,
        )

    async def cancel_task(self, task_id: int, user_id: int) -> bool:
        """Отмена задачи (PENDING или PROCESSING)."""
        task = await self._repo.get_by_id_and_user(task_id, user_id)
        if not task:
            return False
        if task.status not in (TaskStatus.PENDING, TaskStatus.PROCESSING):
            return False
        await self._repo.cancel_task(task_id)
        await self._session.commit()
        return True

    async def retry_task(self, task_id: int, user_id: int) -> Optional[Task]:
        """Повтор задачи (для FAILED). Сбрасывает статус в PENDING и увеличивает retry_count."""
        task = await self._repo.get_by_id_and_user(task_id, user_id)
        if not task or task.status != TaskStatus.FAILED:
            return None
        await self._repo.update_by_id(
            task_id,
            status=TaskStatus.PENDING,
            error_message=None,
            progress=0.0,
            retry_count=task.retry_count + 1,
        )
        await self._session.commit()
        return await self._repo.get_by_id(task_id)

    async def update_status(
        self,
        task_id: int,
        status: TaskStatus,
        error_message: Optional[str] = None,
    ) -> Optional[Task]:
        """Обновление статуса задачи (для воркеров)."""
        updated = await self._repo.update_status(task_id, status, error_message)
        if updated:
            await self._session.commit()
            await self._session.refresh(updated)
        return updated

    async def update_progress(self, task_id: int, progress: float) -> Optional[Task]:
        """Обновление прогресса задачи."""
        updated = await self._repo.update_progress(task_id, progress)
        if updated:
            await self._session.commit()
            await self._session.refresh(updated)
        return updated

    async def update_result(
        self, task_id: int, result: Dict[str, Any]
    ) -> Optional[Task]:
        """Сохранение результата задачи."""
        updated = await self._repo.update_result(task_id, result)
        if updated:
            await self._session.commit()
            await self._session.refresh(updated)
        return updated