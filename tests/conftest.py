"""
Pytest configuration and fixtures for FFmpeg API tests
"""
import pytest
import os
import sys
from unittest.mock import MagicMock, AsyncMock
from typing import AsyncGenerator
import aiosqlite


# Set test environment variables BEFORE any imports
os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:///:memory:'
os.environ['REDIS_URL'] = 'redis://localhost:6379/0'
os.environ['MINIO_ENDPOINT'] = 'localhost:9000'
os.environ['MINIO_ACCESS_KEY'] = 'test_access'
os.environ['MINIO_SECRET_KEY'] = 'test_secret'
os.environ['JWT_SECRET'] = 'test-secret-key-for-testing-only-32chars'


# Create mocks for database connection
mock_engine = MagicMock()
mock_session_maker = MagicMock()
mock_async_session = MagicMock()

# Create mock connection module
class MockConnection:
    engine = mock_engine
    async_session_maker = mock_session_maker
    
    async def get_db():
        yield mock_async_session
    
    @staticmethod
    async def init_db():
        pass
    
    @staticmethod
    async def close_db():
        pass


# Inject mock into sys.modules before app imports
sys.modules['app.database.connection'] = MockConnection()


@pytest.fixture
async def test_db() -> AsyncGenerator:
    """
    Create an in-memory SQLite database for testing

    Yields:
        AsyncSession: SQLAlchemy async session
    """
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy.orm import declarative_base
    from app.database.models import Base, User, Task, File, OperationLog, Metrics
    import asyncio

    # Create in-memory SQLite engine
    engine = create_async_engine(
        'sqlite+aiosqlite:///:memory:',
        echo=False,
        connect_args={"check_same_thread": False}
    )

    # Create session factory
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session and yield it
    async with async_session_maker() as session:
        yield session

    # Cleanup
    await engine.dispose()


@pytest.fixture
async def db_session(test_db):
    """Alias for test_db for backward compatibility"""
    yield test_db


@pytest.fixture
async def sample_user(test_db):
    """Create a sample user for testing"""
    from app.database.models import User
    from app.auth.security import SecurityService

    security = SecurityService()

    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=security.hash_password("TestPassword123"),
        api_key=None,
        settings={},
        is_admin=False,
        is_active=True
    )

    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)

    return user


@pytest.fixture
async def sample_task(test_db, sample_user):
    """Create a sample task for testing"""
    from app.database.models import Task
    from datetime import datetime

    task = Task(
        user_id=sample_user.id,
        type="join",
        status="pending",
        input_files=[],
        output_files=[],
        config={},
        error_message=None,
        progress=0.0,
        result=None,
        retry_count=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

    test_db.add(task)
    await test_db.commit()
    await test_db.refresh(task)

    return task


@pytest.fixture
async def sample_file(test_db, sample_user):
    """Create a sample file for testing"""
    from app.database.models import File
    from datetime import datetime

    file = File(
        user_id=sample_user.id,
        filename="test_video.mp4",
        original_filename="test_video.mp4",
        size=1024000,
        content_type="video/mp4",
        storage_path="/test/path/test_video.mp4",
        metadata={"duration": 120, "resolution": "1920x1080", "codec": "h264"},
        is_deleted=False,
        deleted_at=None,
        created_at=datetime.utcnow()
    )

    test_db.add(file)
    await test_db.commit()
    await test_db.refresh(file)

    return file


@pytest.fixture
async def test_user(test_db):
    """Create a sample user for testing"""
    from app.database.models.user import User
    from app.auth.security import SecurityService

    security = SecurityService()

    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=security.hash_password("TestPassword123"),
        api_key=None,
        settings={},
        is_admin=False,
        is_active=True
    )

    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)

    return user


@pytest.fixture
async def admin_user(test_db):
    """Create an admin user for testing"""
    from app.database.models.user import User
    from app.auth.security import SecurityService

    security = SecurityService()

    user = User(
        username="admin",
        email="admin@example.com",
        hashed_password=security.hash_password("AdminPassword123"),
        api_key=None,
        settings={},
        is_admin=True,
        is_active=True
    )

    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)

    return user


@pytest.fixture
async def auth_token(test_user):
    """Generate auth token for test user"""
    from app.auth.jwt import JWTService
    from datetime import timedelta

    jwt_service = JWTService()
    return jwt_service.create_access_token(
        user_id=test_user.id,
        expires_delta=timedelta(minutes=30)
    )


@pytest.fixture
async def admin_auth_token(admin_user):
    """Generate auth token for admin user"""
    from app.auth.jwt import JWTService
    from datetime import timedelta

    jwt_service = JWTService()
    return jwt_service.create_access_token(
        user_id=admin_user.id,
        expires_delta=timedelta(minutes=30)
    )


@pytest.fixture
async def client(test_db):
    """
    Create an async HTTP client for testing

    Mocks database and external dependencies
    """
    from unittest.mock import AsyncMock, MagicMock
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    # Mock MinIO storage
    from unittest.mock import patch, MagicMock as MockMagicMock

    async def mock_upload_bytes(*args, **kwargs):
        return None

    async def mock_get_file_url(*args, **kwargs):
        return f"http://localhost:9000/bucket/test-file"

    mock_storage = MockMagicMock()
    mock_storage.upload_bytes = AsyncMock(side_effect=mock_upload_bytes)
    mock_storage.get_file_url = AsyncMock(side_effect=mock_get_file_url)
    mock_storage.delete_file = AsyncMock()
    mock_storage.client.get_object = MockMagicMock(return_value=MockMagicMock(read=lambda: b"test content"))

    with patch("app.services.file_service.MinIOClient", return_value=mock_storage):
        with patch("app.storage.minio_client.MinIOClient", return_value=mock_storage):
            # Mock Celery tasks
            with patch("app.api.v1.tasks.join_video_task.delay", return_value=MockMagicMock()):
                with patch("app.api.v1.tasks.text_overlay_task.delay", return_value=MockMagicMock()):
                    with patch("app.api.v1.tasks.video_overlay_task.delay", return_value=MockMagicMock()):
                        with patch("app.api.v1.tasks.audio_overlay_task.delay", return_value=MockMagicMock()):
                            with patch("app.api.v1.tasks.subtitle_task.delay", return_value=MockMagicMock()):
                                with patch("app.api.v1.tasks.combined_task.delay", return_value=MockMagicMock()):
                                    async with AsyncClient(
                                        transport=ASGITransport(app=app),
                                        base_url="http://test"
                                    ) as ac:
                                        yield ac


@pytest.fixture
async def authorized_client(client, auth_token):
    """Create a client with authentication header"""
    import copy
    from httpx import AsyncClient

    # Create new client with auth header
    headers = dict(client.headers)
    headers["Authorization"] = f"Bearer {auth_token}"

    async with AsyncClient(
        transport=client._transport,
        base_url="http://test",
        headers=headers
    ) as ac:
        yield ac


@pytest.fixture
async def admin_client(client, admin_auth_token):
    """Create a client with admin authentication header"""
    from httpx import AsyncClient

    headers = dict(client.headers)
    headers["Authorization"] = f"Bearer {admin_auth_token}"

    async with AsyncClient(
        transport=client._transport,
        base_url="http://test",
        headers=headers
    ) as ac:
        yield ac


@pytest.fixture
async def test_file(test_db, sample_user):
    """Create a sample file for testing"""
    from app.database.models.file import File
    from datetime import datetime

    file = File(
        user_id=sample_user.id,
        filename="test_video.mp4",
        original_filename="test_video.mp4",
        size=1024000,
        content_type="video/mp4",
        storage_path="/test/path/test_video.mp4",
        metadata={"duration": 120, "resolution": "1920x1080", "codec": "h264"},
        is_deleted=False,
        deleted_at=None,
        created_at=datetime.utcnow()
    )

    test_db.add(file)
    await test_db.commit()
    await test_db.refresh(file)

    return file


@pytest.fixture
def temp_video_file(tmp_path):
    """
    Create a temporary test video file using OpenCV

    Returns the path to the created video file
    """
    import numpy as np
    import cv2

    video_path = tmp_path / "test_video.mp4"
    video_path_str = str(video_path)

    # Create a simple video with random colored frames
    width, height = 640, 480
    fps = 30
    duration = 1  # seconds
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')

    out = cv2.VideoCapture(video_path_str, cv2.CAP_FFMPEG)
    writer = cv2.VideoWriter(video_path_str, fourcc, fps, (width, height))

    for frame_idx in range(fps * duration):
        # Create random colored frame
        frame = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
        # Add timestamp text
        cv2.putText(
            frame,
            f"Frame {frame_idx}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 255),
            2
        )
        writer.write(frame)

    writer.release()

    yield video_path_str

    # Cleanup
    if video_path.exists():
        video_path.unlink()


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Setup test environment for all tests"""
    # Additional mocking if needed
    yield
