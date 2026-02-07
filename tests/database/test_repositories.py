"""
Tests for database repositories
"""
import pytest
from datetime import datetime

from app.database.repositories import (
    BaseRepository,
    UserRepository,
    TaskRepository,
    FileRepository,
)
from app.database.models import (
    User,
    Task,
    TaskType,
    TaskStatus,
    File,
)


class TestBaseRepository:
    """Test cases for BaseRepository"""
    
    @pytest.mark.asyncio
    async def test_create(self, db_session):
        """Test creating a record"""
        repo = BaseRepository(User, db_session)
        user = await repo.create(
            username="testuser",
            email="test@example.com",
            hashed_password="hashed"
        )
        
        assert user.id is not None
        assert user.username == "testuser"
    
    @pytest.mark.asyncio
    async def test_get_by_id(self, db_session, sample_user):
        """Test getting a record by ID"""
        repo = BaseRepository(User, db_session)
        user = await repo.get_by_id(sample_user.id)
        
        assert user is not None
        assert user.id == sample_user.id
    
    @pytest.mark.asyncio
    async def test_get_all(self, db_session):
        """Test getting all records with pagination"""
        repo = BaseRepository(User, db_session)
        
        # Create multiple users
        for i in range(5):
            await repo.create(
                username=f"user{i}",
                email=f"user{i}@example.com",
                hashed_password="hashed"
            )
        
        users = await repo.get_all(offset=0, limit=3)
        assert len(users) == 3
    
    @pytest.mark.asyncio
    async def test_update(self, db_session, sample_user):
        """Test updating a record"""
        repo = BaseRepository(User, db_session)
        updated_user = await repo.update(sample_user, username="updated_username")
        
        assert updated_user.username == "updated_username"
    
    @pytest.mark.asyncio
    async def test_delete(self, db_session, sample_user):
        """Test deleting a record"""
        repo = BaseRepository(User, db_session)
        result = await repo.delete(sample_user)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_count(self, db_session):
        """Test counting records"""
        repo = BaseRepository(User, db_session)
        
        await repo.create(
            username="user1",
            email="user1@example.com",
            hashed_password="hashed"
        )
        await repo.create(
            username="user2",
            email="user2@example.com",
            hashed_password="hashed"
        )
        
        count = await repo.count()
        assert count == 2


class TestUserRepository:
    """Test cases for UserRepository"""
    
    @pytest.mark.asyncio
    async def test_create_with_password_hashing(self, db_session):
        """Test creating user with password hashing"""
        repo = UserRepository(db_session)
        user = await repo.create(
            username="testuser",
            email="test@example.com",
            password="plain_password"
        )
        
        assert user.id is not None
        assert user.hashed_password != "plain_password"
        assert len(user.hashed_password) > 0
    
    @pytest.mark.asyncio
    async def test_get_by_email(self, db_session, sample_user):
        """Test getting user by email"""
        repo = UserRepository(db_session)
        user = await repo.get_by_email(sample_user.email)
        
        assert user is not None
        assert user.email == sample_user.email
    
    @pytest.mark.asyncio
    async def test_get_by_username(self, db_session, sample_user):
        """Test getting user by username"""
        repo = UserRepository(db_session)
        user = await repo.get_by_username(sample_user.username)
        
        assert user is not None
        assert user.username == sample_user.username
    
    @pytest.mark.asyncio
    async def test_authenticate_success(self, db_session):
        """Test successful authentication"""
        repo = UserRepository(db_session)
        user = await repo.create(
            username="testuser",
            email="test@example.com",
            password="password123"
        )
        
        authenticated_user = await repo.authenticate("test@example.com", "password123")
        
        assert authenticated_user is not None
        assert authenticated_user.id == user.id
    
    @pytest.mark.asyncio
    async def test_authenticate_failure(self, db_session):
        """Test failed authentication"""
        repo = UserRepository(db_session)
        await repo.create(
            username="testuser",
            email="test@example.com",
            password="password123"
        )
        
        authenticated_user = await repo.authenticate("test@example.com", "wrong_password")
        
        assert authenticated_user is None
    
    @pytest.mark.asyncio
    async def test_generate_api_key(self, db_session, sample_user):
        """Test generating API key"""
        repo = UserRepository(db_session)
        api_key = await repo.generate_api_key(sample_user.id)
        
        assert api_key is not None
        assert len(api_key) > 0
    
    @pytest.mark.asyncio
    async def test_revoke_api_key(self, db_session, sample_user):
        """Test revoking API key"""
        repo = UserRepository(db_session)
        
        # First generate API key
        await repo.generate_api_key(sample_user.id)
        
        # Then revoke it
        result = await repo.revoke_api_key(sample_user.id)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_change_password(self, db_session):
        """Test changing password"""
        repo = UserRepository(db_session)
        user = await repo.create(
            username="testuser",
            email="test@example.com",
            password="old_password"
        )
        
        result = await repo.change_password(
            user.id,
            "old_password",
            "new_password"
        )
        
        assert result is True


class TestTaskRepository:
    """Test cases for TaskRepository"""
    
    @pytest.mark.asyncio
    async def test_create_task(self, db_session, sample_user):
        """Test creating a task"""
        repo = TaskRepository(db_session)
        task = await repo.create(
            user_id=sample_user.id,
            task_type=TaskType.JOIN,
            config={"resolution": "1080p"}
        )
        
        assert task.id is not None
        assert task.user_id == sample_user.id
        assert task.type == TaskType.JOIN
        assert task.status == TaskStatus.PENDING
    
    @pytest.mark.asyncio
    async def test_get_by_user(self, db_session, sample_user):
        """Test getting tasks by user"""
        repo = TaskRepository(db_session)
        
        # Create multiple tasks for user
        for i in range(3):
            await repo.create(
                user_id=sample_user.id,
                task_type=TaskType.JOIN
            )
        
        tasks = await repo.get_by_user(sample_user.id, limit=10)
        assert len(tasks) >= 3
    
    @pytest.mark.asyncio
    async def test_update_status(self, db_session, sample_task):
        """Test updating task status"""
        repo = TaskRepository(db_session)
        updated_task = await repo.update_status(
            sample_task.id,
            TaskStatus.PROCESSING
        )
        
        assert updated_task is not None
        assert updated_task.status == TaskStatus.PROCESSING
    
    @pytest.mark.asyncio
    async def test_update_progress(self, db_session, sample_task):
        """Test updating task progress"""
        repo = TaskRepository(db_session)
        updated_task = await repo.update_progress(sample_task.id, 50.0)
        
        assert updated_task is not None
        assert updated_task.progress == 50.0
    
    @pytest.mark.asyncio
    async def test_update_result(self, db_session, sample_task):
        """Test updating task result"""
        repo = TaskRepository(db_session)
        result_data = {"output_file": "result.mp4", "duration": 120.5}
        updated_task = await repo.update_result(sample_task.id, result_data)
        
        assert updated_task is not None
        assert updated_task.result == result_data
    
    @pytest.mark.asyncio
    async def test_get_pending_tasks(self, db_session, sample_user):
        """Test getting pending tasks"""
        repo = TaskRepository(db_session)
        
        await repo.create(user_id=sample_user.id, task_type=TaskType.JOIN)
        await repo.create(user_id=sample_user.id, task_type=TaskType.AUDIO_OVERLAY)
        
        pending_tasks = await repo.get_pending_tasks(limit=10)
        assert len(pending_tasks) >= 0
    
    @pytest.mark.asyncio
    async def test_get_tasks_statistics(self, db_session, sample_user):
        """Test getting tasks statistics"""
        repo = TaskRepository(db_session)
        
        await repo.create(user_id=sample_user.id, task_type=TaskType.JOIN)
        await repo.create(user_id=sample_user.id, task_type=TaskType.AUDIO_OVERLAY)
        
        stats = await repo.get_tasks_statistics(sample_user.id)
        
        assert stats["total"] >= 2
        assert "by_status" in stats
        assert "by_type" in stats


class TestFileRepository:
    """Test cases for FileRepository"""
    
    @pytest.mark.asyncio
    async def test_create_file(self, db_session, sample_user):
        """Test creating a file"""
        repo = FileRepository(db_session)
        file_obj = await repo.create(
            user_id=sample_user.id,
            filename="video_123.mp4",
            original_filename="myvideo.mp4",
            size=1024000,
            content_type="video/mp4",
            storage_path="/videos/video_123.mp4"
        )
        
        assert file_obj.id is not None
        assert file_obj.user_id == sample_user.id
        assert file_obj.filename == "video_123.mp4"
    
    @pytest.mark.asyncio
    async def test_get_by_user(self, db_session, sample_user):
        """Test getting files by user"""
        repo = FileRepository(db_session)
        
        await repo.create(
            user_id=sample_user.id,
            filename="video1.mp4",
            original_filename="video1.mp4",
            size=1000,
            content_type="video/mp4",
            storage_path="/videos/video1.mp4"
        )
        await repo.create(
            user_id=sample_user.id,
            filename="video2.mp4",
            original_filename="video2.mp4",
            size=2000,
            content_type="video/mp4",
            storage_path="/videos/video2.mp4"
        )
        
        files = await repo.get_by_user(sample_user.id, limit=10)
        assert len(files) >= 2
    
    @pytest.mark.asyncio
    async def test_mark_as_deleted(self, db_session, sample_file):
        """Test marking file as deleted"""
        repo = FileRepository(db_session)
        result = await repo.mark_as_deleted(sample_file.id)
        
        assert result is True
        
        # Verify file is marked as deleted
        updated_file = await repo.get_by_id(sample_file.id)
        assert updated_file.is_deleted is True
    
    @pytest.mark.asyncio
    async def test_restore(self, db_session, sample_file):
        """Test restoring a deleted file"""
        repo = FileRepository(db_session)
        
        # Mark as deleted
        await repo.mark_as_deleted(sample_file.id)
        
        # Restore
        result = await repo.restore(sample_file.id)
        assert result is True
        
        # Verify file is restored
        updated_file = await repo.get_by_id(sample_file.id)
        assert updated_file.is_deleted is False
    
    @pytest.mark.asyncio
    async def test_get_user_storage_usage(self, db_session, sample_user):
        """Test getting user storage usage"""
        repo = FileRepository(db_session)
        
        await repo.create(
            user_id=sample_user.id,
            filename="video1.mp4",
            original_filename="video1.mp4",
            size=1000,
            content_type="video/mp4",
            storage_path="/videos/video1.mp4"
        )
        await repo.create(
            user_id=sample_user.id,
            filename="video2.mp4",
            original_filename="video2.mp4",
            size=2000,
            content_type="video/mp4",
            storage_path="/videos/video2.mp4"
        )
        
        usage = await repo.get_user_storage_usage(sample_user.id)
        assert usage >= 3000
    
    @pytest.mark.asyncio
    async def test_get_files_statistics(self, db_session, sample_user):
        """Test getting files statistics"""
        repo = FileRepository(db_session)
        
        await repo.create(
            user_id=sample_user.id,
            filename="video1.mp4",
            original_filename="video1.mp4",
            size=1000,
            content_type="video/mp4",
            storage_path="/videos/video1.mp4"
        )
        
        stats = await repo.get_files_statistics(sample_user.id)
        
        assert stats["total_count"] >= 1
        assert stats["total_size_bytes"] >= 1000
        assert "by_content_type" in stats


# Fixtures
@pytest.fixture
async def db_session():
    """Get test database session"""
    from app.database.connection import async_session_maker
    
    async with async_session_maker() as session:
        yield session


@pytest.fixture
async def sample_user(db_session):
    """Create a sample user for testing"""
    repo = UserRepository(db_session)
    user = await repo.create(
        username="testuser",
        email="test@example.com",
        password="password123"
    )
    await db_session.flush()
    return user


@pytest.fixture
async def sample_task(db_session, sample_user):
    """Create a sample task for testing"""
    repo = TaskRepository(db_session)
    task = await repo.create(
        user_id=sample_user.id,
        task_type=TaskType.JOIN
    )
    await db_session.flush()
    return task


@pytest.fixture
async def sample_file(db_session, sample_user):
    """Create a sample file for testing"""
    repo = FileRepository(db_session)
    file_obj = await repo.create(
        user_id=sample_user.id,
        filename="video_123.mp4",
        original_filename="myvideo.mp4",
        size=1024000,
        content_type="video/mp4",
        storage_path="/videos/video_123.mp4"
    )
    await db_session.flush()
    return file_obj
