"""
Unit tests for TaskRepository
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.repositories.task_repository import TaskRepository
from app.database.models.task import Task, TaskType, TaskStatus
from datetime import datetime, timedelta


@pytest.mark.asyncio
class TestTaskRepository:
    """Tests for TaskRepository"""

    async def test_create_task_success(self, test_db: AsyncSession, test_user):
        """Test successful task creation"""
        repo = TaskRepository(test_db)

        task = await repo.create(
            user_id=test_user.id,
            type=TaskType.JOIN,
            status=TaskStatus.PENDING,
            input_files=[1, 2],
            config={"output_filename": "test.mp4"}
        )

        assert task is not None
        assert task.user_id == test_user.id
        assert task.type == TaskType.JOIN
        assert task.status == TaskStatus.PENDING
        assert task.input_files == [1, 2]
        assert task.config["output_filename"] == "test.mp4"

    async def test_get_by_id_success(self, test_db: AsyncSession, sample_task: Task):
        """Test getting task by ID"""
        repo = TaskRepository(test_db)

        task = await repo.get_by_id(sample_task.id)

        assert task is not None
        assert task.id == sample_task.id
        assert task.type == sample_task.type

    async def test_get_by_id_not_found(self, test_db: AsyncSession):
        """Test getting non-existent task by ID"""
        repo = TaskRepository(test_db)

        task = await repo.get_by_id(99999)

        assert task is None

    async def test_get_by_user_id_success(
        self,
        test_db: AsyncSession,
        sample_task: Task,
        sample_user
    ):
        """Test getting tasks by user ID"""
        repo = TaskRepository(test_db)

        tasks = await repo.get_by_user_id(sample_user.id)

        assert isinstance(tasks, list)
        assert len(tasks) > 0
        assert any(t.id == sample_task.id for t in tasks)

    async def test_get_by_user_id_with_filters(
        self,
        test_db: AsyncSession,
        sample_user
    ):
        """Test getting tasks by user ID with status filter"""
        repo = TaskRepository(test_db)

        # Create tasks with different statuses
        await repo.create(
            user_id=sample_user.id,
            type=TaskType.JOIN,
            status=TaskStatus.PENDING,
            input_files=[1],
            config={}
        )
        await repo.create(
            user_id=sample_user.id,
            type=TaskType.JOIN,
            status=TaskStatus.COMPLETED,
            input_files=[2],
            config={}
        )

        pending_tasks = await repo.get_by_user_id(
            sample_user.id,
            status=TaskStatus.PENDING
        )

        assert all(t.status == TaskStatus.PENDING for t in pending_tasks)

    async def test_update_task_success(self, test_db: AsyncSession, sample_task: Task):
        """Test updating task"""
        repo = TaskRepository(test_db)

        updated = await repo.update(
            sample_task.id,
            {
                "status": TaskStatus.PROCESSING,
                "progress": 50.0
            }
        )

        assert updated is True

        # Verify update
        await test_db.refresh(sample_task)
        assert sample_task.status == TaskStatus.PROCESSING
        assert sample_task.progress == 50.0

    async def test_update_task_not_found(self, test_db: AsyncSession):
        """Test updating non-existent task"""
        repo = TaskRepository(test_db)

        updated = await repo.update(
            99999,
            {"status": TaskStatus.PROCESSING}
        )

        assert updated is False

    async def test_increment_progress_success(
        self,
        test_db: AsyncSession,
        sample_task: Task
    ):
        """Test incrementing task progress"""
        repo = TaskRepository(test_db)

        await repo.increment_progress(sample_task.id, 25.0)

        # Verify update
        await test_db.refresh(sample_task)
        assert sample_task.progress == 25.0

    async def test_update_status_success(
        self,
        test_db: AsyncSession,
        sample_task: Task
    ):
        """Test updating task status"""
        repo = TaskRepository(test_db)

        await repo.update_status(sample_task.id, TaskStatus.PROCESSING)

        # Verify update
        await test_db.refresh(sample_task)
        assert sample_task.status == TaskStatus.PROCESSING

    async def test_set_task_result_success(
        self,
        test_db: AsyncSession,
        sample_task: Task
    ):
        """Test setting task result"""
        repo = TaskRepository(test_db)

        result = {
            "output_file": "result.mp4",
            "duration": 120.5
        }

        await repo.set_result(
            sample_task.id,
            TaskStatus.COMPLETED,
            result
        )

        # Verify update
        await test_db.refresh(sample_task)
        assert sample_task.status == TaskStatus.COMPLETED
        assert sample_task.result == result
        assert sample_task.progress == 100.0

    async def test_set_task_error_success(
        self,
        test_db: AsyncSession,
        sample_task: Task
    ):
        """Test setting task error"""
        repo = TaskRepository(test_db)

        error_message = "Processing failed"

        await repo.set_error(
            sample_task.id,
            TaskStatus.FAILED,
            error_message
        )

        # Verify update
        await test_db.refresh(sample_task)
        assert sample_task.status == TaskStatus.FAILED
        assert sample_task.error_message == error_message

    async def test_increment_retry_count(
        self,
        test_db: AsyncSession,
        sample_task: Task
    ):
        """Test incrementing retry count"""
        repo = TaskRepository(test_db)

        initial_count = sample_task.retry_count

        await repo.increment_retry(sample_task.id)

        # Verify update
        await test_db.refresh(sample_task)
        assert sample_task.retry_count == initial_count + 1

    async def test_delete_task_success(self, test_db: AsyncSession, sample_task: Task):
        """Test deleting task"""
        repo = TaskRepository(test_db)

        deleted = await repo.delete(sample_task.id)

        assert deleted is True

        # Verify deletion
        task = await repo.get_by_id(sample_task.id)
        assert task is None

    async def test_delete_task_not_found(self, test_db: AsyncSession):
        """Test deleting non-existent task"""
        repo = TaskRepository(test_db)

        deleted = await repo.delete(99999)

        assert deleted is False

    async def test_list_tasks_success(
        self,
        test_db: AsyncSession,
        sample_task: Task
    ):
        """Test listing tasks"""
        repo = TaskRepository(test_db)

        tasks = await repo.list(limit=10, offset=0)

        assert isinstance(tasks, list)
        assert len(tasks) > 0
        assert any(t.id == sample_task.id for t in tasks)

    async def test_list_tasks_with_pagination(self, test_db: AsyncSession):
        """Test listing tasks with pagination"""
        repo = TaskRepository(test_db)

        tasks = await repo.list(limit=1, offset=0)

        assert len(tasks) <= 1

    async def test_count_tasks(self, test_db: AsyncSession):
        """Test counting tasks"""
        repo = TaskRepository(test_db)

        count = await repo.count()

        assert isinstance(count, int)
        assert count >= 1

    async def test_get_old_pending_tasks(self, test_db: AsyncSession, sample_user):
        """Test getting old pending tasks"""
        repo = TaskRepository(test_db)

        # Create an old pending task
        old_task = await repo.create(
            user_id=sample_user.id,
            type=TaskType.JOIN,
            status=TaskStatus.PENDING,
            input_files=[1],
            config={}
        )

        # Manually set created_at to old date
        old_time = datetime.utcnow() - timedelta(hours=2)
        old_task.created_at = old_time
        old_task.updated_at = old_time
        await test_db.commit()

        # Get old tasks
        old_tasks = await repo.get_old_pending_tasks(minutes=60)

        assert len(old_tasks) >= 1
        assert any(t.id == old_task.id for t in old_tasks)

    async def test_get_tasks_by_status(
        self,
        test_db: AsyncSession,
        sample_task: Task
    ):
        """Test getting tasks by status"""
        repo = TaskRepository(test_db)

        pending_tasks = await repo.get_by_status(TaskStatus.PENDING)

        assert isinstance(pending_tasks, list)
        assert all(t.status == TaskStatus.PENDING for t in pending_tasks)
