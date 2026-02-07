"""
Task repository for task-related database operations
"""
from typing import List, Optional, Any, Dict
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, func, select

from app.database.repositories.base import BaseRepository
from app.database.models.task import Task, TaskStatus, TaskType


class TaskRepository(BaseRepository[Task]):
    """
    Repository for Task model operations
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize TaskRepository
        
        Args:
            session: Async database session
        """
        super().__init__(Task, session)
    
    async def create(
        self,
        user_id: int,
        task_type: TaskType,
        config: Optional[Dict[str, Any]] = None,
        input_files: Optional[list] = None,
        output_files: Optional[list] = None,
        priority: int = 5,
        **kwargs: Any
    ) -> Task:
        """
        Create a new task

        Args:
            user_id: User ID
            task_type: Task type
            config: Task configuration
            input_files: List of input file IDs
            output_files: List of output file IDs
            priority: Task priority (1-10)
            **kwargs: Additional task fields

        Returns:
            Created task instance
        """
        task = Task(
            user_id=user_id,
            type=task_type,
            config=config or {},
            input_files=input_files or [],
            output_files=output_files or [],
            priority=priority,
            **kwargs
        )
        self.session.add(task)
        await self.session.flush()
        await self.session.refresh(task)
        return task
    
    async def get_by_user(
        self,
        user_id: int,
        offset: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Task]:
        """
        Get tasks for a specific user with pagination and filtering
        
        Args:
            user_id: User ID
            offset: Number of tasks to skip
            limit: Maximum number of tasks to return
            filters: Additional filters (status, type, etc.)
            
        Returns:
            List of task instances
        """
        stmt = select(Task).where(Task.user_id == user_id)
        
        # Apply filters
        if filters:
            for key, value in filters.items():
                if hasattr(Task, key):
                    stmt = stmt.where(getattr(Task, key) == value)
        
        stmt = stmt.offset(offset).limit(limit)
        stmt = stmt.order_by(Task.created_at.desc())
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id_and_user(self, task_id: int, user_id: int) -> Optional[Task]:
        """
        Get task by ID and user ID.

        Args:
            task_id: Task ID
            user_id: User ID

        Returns:
            Task instance or None if not found / not owned by user
        """
        stmt = select(Task).where(
            Task.id == task_id,
            Task.user_id == user_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_by_user(
        self,
        user_id: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Count tasks for user with optional filters.

        Args:
            user_id: User ID
            filters: Optional filters (status, type)

        Returns:
            Total count
        """
        stmt = select(func.count(Task.id)).where(Task.user_id == user_id)
        if filters:
            for key, value in filters.items():
                if hasattr(Task, key):
                    stmt = stmt.where(getattr(Task, key) == value)
        result = await self.session.execute(stmt)
        return result.scalar() or 0
    
    async def get_by_status(self, status: TaskStatus) -> List[Task]:
        """
        Get tasks by status
        
        Args:
            status: Task status
            
        Returns:
            List of task instances
        """
        stmt = select(Task).where(Task.status == status)
        stmt = stmt.order_by(Task.created_at.asc())
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_by_type(self, task_type: TaskType) -> List[Task]:
        """
        Get tasks by type
        
        Args:
            task_type: Task type
            
        Returns:
            List of task instances
        """
        stmt = select(Task).where(Task.type == task_type)
        stmt = stmt.order_by(Task.created_at.desc())
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_by_user_and_status(
        self,
        user_id: int,
        status: TaskStatus,
        offset: int = 0,
        limit: int = 100
    ) -> List[Task]:
        """
        Get tasks for a user by status
        
        Args:
            user_id: User ID
            status: Task status
            offset: Number of tasks to skip
            limit: Maximum number of tasks to return
            
        Returns:
            List of task instances
        """
        stmt = select(Task).where(
            Task.user_id == user_id,
            Task.status == status
        )
        stmt = stmt.offset(offset).limit(limit)
        stmt = stmt.order_by(Task.created_at.desc())
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def update_status(
        self,
        task_id: int,
        status: TaskStatus,
        error_message: Optional[str] = None
    ) -> Optional[Task]:
        """
        Update task status
        
        Args:
            task_id: Task ID
            status: New status
            error_message: Error message if status is failed
            
        Returns:
            Updated task instance or None if not found
        """
        update_data: Dict[str, Any] = {"status": status}
        
        if status == TaskStatus.COMPLETED:
            update_data["completed_at"] = datetime.utcnow()
            update_data["progress"] = 100.0
        elif status == TaskStatus.FAILED and error_message:
            update_data["error_message"] = error_message
        elif status == TaskStatus.PROCESSING:
            update_data["progress"] = 0.0
        
        return await self.update_by_id(task_id, **update_data)
    
    async def update_progress(
        self,
        task_id: int,
        progress: float
    ) -> Optional[Task]:
        """
        Update task progress
        
        Args:
            task_id: Task ID
            progress: Progress value (0.0-100.0)
            
        Returns:
            Updated task instance or None if not found
        """
        return await self.update_by_id(task_id, progress=progress)
    
    async def update_result(
        self,
        task_id: int,
        result: Dict[str, Any]
    ) -> Optional[Task]:
        """
        Update task result
        
        Args:
            task_id: Task ID
            result: Task result data
            
        Returns:
            Updated task instance or None if not found
        """
        return await self.update_by_id(task_id, result=result)
    
    async def get_pending_tasks(self, limit: int = 10) -> List[Task]:
        """
        Get pending tasks ordered by creation time
        
        Args:
            limit: Maximum number of tasks to return
            
        Returns:
            List of pending task instances
        """
        stmt = select(Task).where(Task.status == TaskStatus.PENDING)
        stmt = stmt.order_by(Task.created_at.asc())
        stmt = stmt.limit(limit)
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    
    async def get_tasks_statistics(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get tasks statistics
        
        Args:
            user_id: Optional user ID to filter stats
            
        Returns:
            Dictionary with statistics
        """
        stmt = select(Task)
        
        if user_id:
            stmt = stmt.where(Task.user_id == user_id)
        
        result = await self.session.execute(stmt)
        tasks = result.scalars().all()
        
        stats: Dict[str, Any] = {
            "total": len(tasks),
            "by_status": {},
            "by_type": {},
            "average_retry_count": 0.0
        }
        
        # Count by status
        for status in TaskStatus:
            count = sum(1 for t in tasks if t.status == status)
            stats["by_status"][status.value] = count
        
        # Count by type
        for task_type in TaskType:
            count = sum(1 for t in tasks if t.type == task_type)
            stats["by_type"][task_type.value] = count
        
        # Average retry count
        if tasks:
            stats["average_retry_count"] = sum(t.retry_count for t in tasks) / len(tasks)
        
        return stats
    
    async def increment_retry_count(self, task_id: int) -> Optional[Task]:
        """
        Increment task retry count
        
        Args:
            task_id: Task ID
            
        Returns:
            Updated task instance or None if not found
        """
        task = await self.get_by_id(task_id)
        if task:
            return await self.update(task, retry_count=task.retry_count + 1)
        return None
    
    async def get_user_active_tasks_count(self, user_id: int) -> int:
        """
        Get count of active tasks for a user
        
        Args:
            user_id: User ID
            
        Returns:
            Number of active tasks
        """
        active_statuses = [TaskStatus.PENDING, TaskStatus.PROCESSING]
        stmt = select(func.count(Task.id)).where(
            Task.user_id == user_id,
            Task.status.in_(active_statuses)
        )
        
        result = await self.session.execute(stmt)
        return result.scalar() or 0
    
    async def cancel_task(self, task_id: int) -> Optional[Task]:
        """
        Cancel a task
        
        Args:
            task_id: Task ID
            
        Returns:
            Updated task instance or None if not found
        """
        return await self.update_status(task_id, TaskStatus.CANCELLED)
    
    async def get_all_tasks(
        self,
        status: Optional[TaskStatus] = None,
        user_id: Optional[int] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Any:
        """
        Список всех задач с фильтрами (для админки).
        Returns: объект с полями tasks (list) и total (int).
        """
        stmt = select(Task)
        count_stmt = select(func.count(Task.id))
        if status is not None:
            stmt = stmt.where(Task.status == status)
            count_stmt = count_stmt.where(Task.status == status)
        if user_id is not None:
            stmt = stmt.where(Task.user_id == user_id)
            count_stmt = count_stmt.where(Task.user_id == user_id)
        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0
        stmt = stmt.offset(offset).limit(limit).order_by(Task.created_at.desc())
        result = await self.session.execute(stmt)
        tasks = list(result.scalars().all())
        return type("Result", (), {"tasks": tasks, "total": total})()

    async def get_all_tasks_statistics(self) -> Dict[str, Any]:
        """Статистика по всем задачам (без фильтра user_id)."""
        return await self.get_tasks_statistics(user_id=None)

    async def delete_tasks_older_than(self, cutoff_date: datetime) -> int:
        """
        Удаление записей задач старше указанной даты. Возвращает количество удалённых.
        """
        stmt = delete(Task).where(Task.created_at < cutoff_date)
        result = await self.session.execute(stmt)
        return result.rowcount or 0

    async def get_completed_tasks_in_period(
        self,
        user_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Task]:
        """
        Get completed tasks within a time period
        
        Args:
            user_id: Optional user ID to filter
            start_date: Start of period
            end_date: End of period
            
        Returns:
            List of completed task instances
        """
        stmt = select(Task).where(Task.status == TaskStatus.COMPLETED)
        
        if user_id:
            stmt = stmt.where(Task.user_id == user_id)
        
        if start_date:
            stmt = stmt.where(Task.completed_at >= start_date)
        
        if end_date:
            stmt = stmt.where(Task.completed_at <= end_date)
        
        stmt = stmt.order_by(Task.completed_at.desc())
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
