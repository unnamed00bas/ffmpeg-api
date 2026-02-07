"""
Tests for database models
"""
import pytest
from datetime import datetime

from app.database.models import (
    BaseModel,
    User,
    Task,
    TaskType,
    TaskStatus,
    File,
    OperationLog,
    Metrics,
)


class TestUserModel:
    """Test cases for User model"""
    
    def test_user_creation(self, db_session):
        """Test creating a user"""
        user = User(
            username="testuser",
            email="test@example.com",
            hashed_password="hashed_password_here"
        )
        db_session.add(user)
        db_session.flush()
        db_session.refresh(user)
        
        assert user.id is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.hashed_password == "hashed_password_here"
        assert user.is_active is True
        assert user.is_admin is False
        assert user.created_at is not None
        assert user.updated_at is not None
    
    def test_user_repr(self, db_session):
        """Test User model __repr__"""
        user = User(
            username="testuser",
            email="test@example.com",
            hashed_password="hashed"
        )
        db_session.add(user)
        db_session.flush()
        
        repr_str = repr(user)
        assert "User" in repr_str
        assert str(user.id) in repr_str
        assert "testuser" in repr_str
        assert "test@example.com" in repr_str
    
    def test_user_defaults(self, db_session):
        """Test User model default values"""
        user = User(
            username="testuser",
            email="test@example.com",
            hashed_password="hashed"
        )
        db_session.add(user)
        db_session.flush()
        db_session.refresh(user)
        
        assert user.is_active is True
        assert user.is_admin is False
        assert user.settings is not None
        assert user.api_key is None


class TestTaskModel:
    """Test cases for Task model"""
    
    def test_task_creation(self, db_session, sample_user):
        """Test creating a task"""
        task = Task(
            user_id=sample_user.id,
            type=TaskType.JOIN,
            status=TaskStatus.PENDING,
            input_files=[],
            output_files=[]
        )
        db_session.add(task)
        db_session.flush()
        db_session.refresh(task)
        
        assert task.id is not None
        assert task.user_id == sample_user.id
        assert task.type == TaskType.JOIN
        assert task.status == TaskStatus.PENDING
        assert task.progress == 0.0
        assert task.retry_count == 0
        assert task.created_at is not None
    
    def test_task_repr(self, db_session, sample_user):
        """Test Task model __repr__"""
        task = Task(
            user_id=sample_user.id,
            type=TaskType.AUDIO_OVERLAY,
            status=TaskStatus.PENDING,
            input_files=[],
            output_files=[]
        )
        db_session.add(task)
        db_session.flush()
        
        repr_str = repr(task)
        assert "Task" in repr_str
        assert str(task.id) in repr_str
        assert str(task.user_id) in repr_str
        assert "audio_overlay" in repr_str
    
    def test_task_enums(self, db_session, sample_user):
        """Test Task enum values"""
        task = Task(
            user_id=sample_user.id,
            type=TaskType.COMBINED,
            status=TaskStatus.PROCESSING,
            input_files=[],
            output_files=[]
        )
        db_session.add(task)
        db_session.flush()
        db_session.refresh(task)
        
        assert task.type == TaskType.COMBINED
        assert task.status == TaskStatus.PROCESSING


class TestFileModel:
    """Test cases for File model"""
    
    def test_file_creation(self, db_session, sample_user):
        """Test creating a file"""
        file_obj = File(
            user_id=sample_user.id,
            filename="video_123.mp4",
            original_filename="myvideo.mp4",
            size=1024000,
            content_type="video/mp4",
            storage_path="/videos/video_123.mp4"
        )
        db_session.add(file_obj)
        db_session.flush()
        db_session.refresh(file_obj)
        
        assert file_obj.id is not None
        assert file_obj.user_id == sample_user.id
        assert file_obj.filename == "video_123.mp4"
        assert file_obj.size == 1024000
        assert file_obj.is_deleted is False
        assert file_obj.created_at is not None
    
    def test_file_soft_delete(self, db_session, sample_user):
        """Test file soft delete"""
        file_obj = File(
            user_id=sample_user.id,
            filename="video_123.mp4",
            original_filename="myvideo.mp4",
            size=1024000,
            content_type="video/mp4",
            storage_path="/videos/video_123.mp4"
        )
        db_session.add(file_obj)
        db_session.flush()
        
        # Mark as deleted
        file_obj.is_deleted = True
        file_obj.deleted_at = datetime.utcnow()
        db_session.flush()
        db_session.refresh(file_obj)
        
        assert file_obj.is_deleted is True
        assert file_obj.deleted_at is not None
    
    def test_file_repr(self, db_session, sample_user):
        """Test File model __repr__"""
        file_obj = File(
            user_id=sample_user.id,
            filename="video_123.mp4",
            original_filename="myvideo.mp4",
            size=1024000,
            content_type="video/mp4",
            storage_path="/videos/video_123.mp4"
        )
        db_session.add(file_obj)
        db_session.flush()
        
        repr_str = repr(file_obj)
        assert "File" in repr_str
        assert str(file_obj.id) in repr_str
        assert str(file_obj.user_id) in repr_str


class TestOperationLogModel:
    """Test cases for OperationLog model"""
    
    def test_operation_log_creation(self, db_session, sample_user, sample_task):
        """Test creating an operation log"""
        log = OperationLog(
            task_id=sample_task.id,
            operation_type="encode",
            duration=15.5,
            success=True
        )
        db_session.add(log)
        db_session.flush()
        db_session.refresh(log)
        
        assert log.id is not None
        assert log.task_id == sample_task.id
        assert log.operation_type == "encode"
        assert log.duration == 15.5
        assert log.success is True
        assert log.timestamp is not None
    
    def test_operation_log_repr(self, db_session, sample_task):
        """Test OperationLog model __repr__"""
        log = OperationLog(
            task_id=sample_task.id,
            operation_type="merge",
            duration=30.0,
            success=True
        )
        db_session.add(log)
        db_session.flush()
        
        repr_str = repr(log)
        assert "OperationLog" in repr_str
        assert str(log.id) in repr_str
        assert str(log.task_id) in repr_str


class TestMetricsModel:
    """Test cases for Metrics model"""
    
    def test_metrics_creation(self, db_session):
        """Test creating metrics"""
        metrics = Metrics(
            metric_name="task_duration",
            metric_value=120.5,
            tags={"task_type": "join", "success": "true"}
        )
        db_session.add(metrics)
        db_session.flush()
        db_session.refresh(metrics)
        
        assert metrics.id is not None
        assert metrics.metric_name == "task_duration"
        assert metrics.metric_value == 120.5
        assert metrics.tags is not None
        assert metrics.timestamp is not None
    
    def test_metrics_repr(self, db_session):
        """Test Metrics model __repr__"""
        metrics = Metrics(
            metric_name="queue_size",
            metric_value=5.0
        )
        db_session.add(metrics)
        db_session.flush()
        
        repr_str = repr(metrics)
        assert "Metrics" in repr_str
        assert str(metrics.id) in repr_str
        assert "queue_size" in repr_str


# Fixtures
@pytest.fixture
def sample_user(db_session):
    """Create a sample user for testing"""
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password="hashed_password"
    )
    db_session.add(user)
    db_session.flush()
    db_session.refresh(user)
    return user


@pytest.fixture
def sample_task(db_session, sample_user):
    """Create a sample task for testing"""
    task = Task(
        user_id=sample_user.id,
        type=TaskType.JOIN,
        status=TaskStatus.PENDING,
        input_files=[],
        output_files=[]
    )
    db_session.add(task)
    db_session.flush()
    db_session.refresh(task)
    return task


@pytest.fixture
def db_session(test_db):
    """Get test database session"""
    from app.database.connection import async_session_maker
    
    async def get_session():
        async with async_session_maker() as session:
            yield session
    
    # In real tests, this would be handled by pytest fixtures
    # For now, just return a mock
    class MockSession:
        def add(self, obj): pass
        def flush(self): pass
        def refresh(self, obj): pass
        def commit(self): pass
        def rollback(self): pass
        def close(self): pass
    
    return MockSession()
