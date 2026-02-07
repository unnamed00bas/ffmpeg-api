"""
Тесты ChunkUploadManager: инициация, чанки, сборка, отмена.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from app.services.chunk_upload import ChunkUploadManager


@pytest.fixture
def mock_redis():
    return MagicMock()


@pytest.fixture
def mock_minio():
    storage = MagicMock()
    storage.upload_bytes = AsyncMock()
    storage.get_object_bytes = AsyncMock(return_value=b"chunk")
    storage.delete_file = AsyncMock()
    return storage


@pytest.fixture
def chunk_manager(mock_redis, mock_minio):
    with patch("app.services.chunk_upload.Redis.from_url", return_value=mock_redis):
        with patch("app.services.chunk_upload.MinIOClient", return_value=mock_minio):
            return ChunkUploadManager()


class TestChunkUploadManager:
    """Unit тесты ChunkUploadManager."""

    @pytest.mark.asyncio
    async def test_initiate_upload_returns_upload_id(self, chunk_manager, mock_redis):
        """initiate_upload создаёт запись в Redis и возвращает upload_id."""
        mock_redis.setex.return_value = None
        upload_id = await chunk_manager.initiate_upload(
            user_id=1,
            filename="test.mp4",
            total_size=1024,
            total_chunks=3,
            content_type="video/mp4",
        )
        assert isinstance(upload_id, str)
        assert len(upload_id) == 36  # uuid hex
        mock_redis.setex.assert_called_once()
        args, kwargs = mock_redis.setex.call_args
        info = json.loads(kwargs["value"])
        assert info["user_id"] == 1
        assert info["filename"] == "test.mp4"
        assert info["total_size"] == 1024
        assert info["total_chunks"] == 3
        assert info["content_type"] == "video/mp4"
        assert info["uploaded_chunks"] == []

    @pytest.mark.asyncio
    async def test_upload_chunk_saves_to_minio_and_updates_state(self, chunk_manager, mock_redis, mock_minio):
        """upload_chunk сохраняет чанк в MinIO и обновляет состояние."""
        mock_redis.get.return_value = json.dumps({
            "user_id": 1,
            "filename": "test.mp4",
            "total_size": 1024,
            "total_chunks": 2,
            "content_type": "video/mp4",
            "uploaded_chunks": [],
            "created_at": datetime.utcnow().isoformat(),
        }).encode()
        mock_redis.setex.return_value = None
        await chunk_manager.upload_chunk("upload-123", 0, b"chunk0")
        mock_minio.upload_bytes.assert_called_once()
        # MinIO object name
        call_args = mock_minio.upload_bytes.call_args
        obj_name = call_args[0][1]
        assert obj_name.startswith("temp/chunks/upload-123_")
        assert obj_name.endswith("_0")
        mock_redis.setex.assert_called_once()
        updated_info = json.loads(mock_redis.setex.call_args[0][2])
        assert [0] in updated_info["uploaded_chunks"]

    @pytest.mark.asyncio
    async def test_upload_chunk_returns_false_for_missing_upload(self, chunk_manager, mock_redis):
        """upload_chunk возвращает False если загрузка не существует."""
        mock_redis.get.return_value = None
        result = await chunk_manager.upload_chunk("missing", 0, b"data")
        assert result is False

    @pytest.mark.asyncio
    async def test_complete_upload_assembles_chunks(self, chunk_manager, mock_redis, mock_minio):
        """complete_upload собирает чанки, загружает в MinIO, создаёт File."""
        mock_redis.get.return_value = json.dumps({
            "user_id": 2,
            "filename": "final.mp4",
            "total_size": 20,
            "total_chunks": 2,
            "content_type": "video/mp4",
            "uploaded_chunks": [0, 1],
            "created_at": datetime.utcnow().isoformat(),
        }).encode()
        mock_minio.get_object_bytes.side_effect = AsyncMock(side_effect=[b"chunk0", b"chunk1"])
        mock_minio.upload_file = AsyncMock()
        mock_redis.delete.return_value = None
        db_mock = MagicMock()
        file_mock = MagicMock(id=10)
        file_mock.storage_path = "storage/path"
        repo_mock = MagicMock()
        repo_mock.create = AsyncMock(return_value=file_mock)
        db_mock.commit = MagicMock()
        db_mock.refresh = MagicMock()
        with patch("app.services.chunk_upload.FileRepository", return_value=repo_mock):
            with patch("app.services.chunk_upload.create_temp_file", return_value="/tmp/merge"):
                result = await chunk_manager.complete_upload("upload-xyz", db_mock)
        # File создан
        repo_mock.create.assert_called_once()
        args = repo_mock.create.call_args[0]
        assert args[0] == 2  # user_id
        assert args[1] == "storage/path"  # storage_path
        assert args[2] == "final.mp4"  # original_filename
        assert args[3] == 20  # size
        assert args[4] == "video/mp4"  # content_type
        # MinIO удалены чанки
        assert mock_minio.delete_file.call_count == 2
        # Redis удалена запись
        mock_redis.delete.assert_called_once_with("chunk_upload:upload-xyz")

    @pytest.mark.asyncio
    async def test_complete_upload_raises_if_not_all_chunks(self, chunk_manager, mock_redis):
        """complete_upload выбрасывает ValueError если не все чанки загружены."""
        mock_redis.get.return_value = json.dumps({
            "uploaded_chunks": [0],
            "total_chunks": 2,
            "user_id": 1,
            "filename": "test.mp4",
            "total_size": 10,
            "content_type": "video/mp4",
            "created_at": datetime.utcnow().isoformat(),
        }).encode()
        with pytest.raises(ValueError, match="Not all chunks uploaded"):
            await chunk_manager.complete_upload("upload-id", MagicMock())

    @pytest.mark.asyncio
    async def test_abort_upload_deletes_chunks_and_redis_record(self, chunk_manager, mock_redis, mock_minio):
        """abort_upload удаляет загруженные чанки и запись Redis."""
        mock_redis.get.return_value = json.dumps({
            "uploaded_chunks": [0, 1],
            "total_chunks": 2,
            "user_id": 1,
            "filename": "test.mp4",
            "total_size": 10,
            "content_type": "video/mp4",
            "created_at": datetime.utcnow().isoformat(),
        }).encode()
        mock_redis.delete.return_value = None
        result = await chunk_manager.abort_upload("upload-abort")
        assert result is True
        assert mock_minio.delete_file.call_count == 2
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_abort_upload_returns_false_for_missing_upload(self, chunk_manager, mock_redis):
        """abort_upload возвращает False если загрузка не существует."""
        mock_redis.get.return_value = None
        result = await chunk_manager.abort_upload("missing")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_upload_info_deserializes_redis_record(self, chunk_manager, mock_redis):
        """get_upload_info десериализует JSON из Redis."""
        info_data = {"user_id": 5, "filename": "test.mp4"}
        mock_redis.get.return_value = json.dumps(info_data).encode()
        info = await chunk_manager.get_upload_info("upload-id")
        assert info == info_data
        mock_redis.get.assert_called_once_with("chunk_upload:upload-id")
