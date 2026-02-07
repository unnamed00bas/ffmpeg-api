"""
Fixtures for integration tests

This module provides fixtures for integration tests that require external services.
"""
import os
import pytest
import asyncio
from pathlib import Path
from typing import AsyncGenerator
from datetime import timedelta

from minio import Minio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base


# Fixtures for MinIO client
@pytest.fixture(scope="session")
def minio_endpoint():
    """Get MinIO endpoint from environment or use default for testing"""
    return os.getenv("MINIO_ENDPOINT", "localhost:9000")


@pytest.fixture(scope="session")
def minio_access_key():
    """Get MinIO access key from environment or use default for testing"""
    return os.getenv("MINIO_ACCESS_KEY", "minioadmin")


@pytest.fixture(scope="session")
def minio_secret_key():
    """Get MinIO secret key from environment or use default for testing"""
    return os.getenv("MINIO_SECRET_KEY", "minioadmin")


@pytest.fixture(scope="session")
def minio_bucket_name():
    """Get MinIO bucket name for testing"""
    return "test-bucket"


@pytest.fixture(scope="function")
def minio_client(minio_endpoint, minio_access_key, minio_secret_key, minio_bucket_name):
    """
    Create a MinIO client for testing

    This fixture provides a real MinIO client for integration tests.
    It creates a test bucket before the test and removes it after.
    """
    client = Minio(
        endpoint=minio_endpoint,
        access_key=minio_access_key,
        secret_key=minio_secret_key,
        secure=False,
    )

    # Create test bucket if it doesn't exist
    if not client.bucket_exists(minio_bucket_name):
        client.make_bucket(minio_bucket_name)

    yield client

    # Cleanup: remove test bucket after test
    # First remove all objects in the bucket
    objects = client.list_objects(minio_bucket_name, recursive=True)
    for obj in objects:
        client.remove_object(minio_bucket_name, obj.object_name)

    # Then remove the bucket
    client.remove_bucket(minio_bucket_name)


@pytest.fixture(scope="function")
async def async_minio_client(minio_endpoint, minio_access_key, minio_secret_key, minio_bucket_name):
    """
    Create an async MinIO client wrapper for testing

    This fixture provides an async wrapper around MinIO client for use in async tests.
    """
    from app.storage.minio_client import MinIOClient
    from unittest.mock import patch

    # Patch settings for testing
    with patch('app.storage.minio_client.settings') as mock_settings:
        mock_settings.MINIO_ENDPOINT = minio_endpoint
        mock_settings.MINIO_ACCESS_KEY = minio_access_key
        mock_settings.MINIO_SECRET_KEY = minio_secret_key
        mock_settings.MINIO_BUCKET_NAME = minio_bucket_name
        mock_settings.MINIO_SECURE = False

        client = MinIOClient()

        yield client

    # Cleanup is handled by minio_client fixture


# Fixtures for PostgreSQL database
@pytest.fixture(scope="session")
def test_database_url():
    """
    Get test database URL from environment

    For integration tests, use a separate test database
    """
    return os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://postgres_user:postgres_password@localhost:5432/test_db"
    )


@pytest.fixture(scope="function")
async def test_engine(test_database_url):
    """
    Create an async engine for testing

    This fixture creates a separate engine for each test function to ensure isolation.
    """
    from app.database.models import Base

    engine = create_async_engine(
        test_database_url,
        echo=False,
        pool_pre_ping=True
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup: drop all tables after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture(scope="function")
async def test_db_session(test_engine):
    """
    Create a database session for testing

    This fixture provides a clean database session for each test.
    """
    async_session_maker = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )

    async with async_session_maker() as session:
        yield session


# Fixtures for sample test data
@pytest.fixture
def sample_video_bytes():
    """
    Provide sample video bytes for testing

    Returns a minimal valid MP4 file for testing upload/download functionality.
    """
    # This is a minimal MP4 header - not a real video but valid for testing file operations
    # In real tests, you would use an actual small video file
    return b'\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00mp42isom\x00\x00\x00\x01\x00\x00\x00\x00'


@pytest.fixture
def sample_audio_bytes():
    """
    Provide sample audio bytes for testing

    Returns a minimal valid MP3 file for testing upload/download functionality.
    """
    # Minimal MP3 header
    return b'ID3\x04\x00\x00\x00\x00\x00\x00' + b'\x00' * 100


@pytest.fixture
def temp_video_file(tmp_path, sample_video_bytes):
    """
    Create a temporary video file for testing

    This fixture creates a temporary video file on disk and returns its path.
    The file is automatically cleaned up after the test.
    """
    video_file = tmp_path / "test_video.mp4"
    video_file.write_bytes(sample_video_bytes)
    return str(video_file)


@pytest.fixture
def temp_audio_file(tmp_path, sample_audio_bytes):
    """
    Create a temporary audio file for testing

    This fixture creates a temporary audio file on disk and returns its path.
    The file is automatically cleaned up after the test.
    """
    audio_file = tmp_path / "test_audio.mp3"
    audio_file.write_bytes(sample_audio_bytes)
    return str(audio_file)
