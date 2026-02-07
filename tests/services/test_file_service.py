"""
Unit tests for FileService with mocked MinIO
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession


class TestFileService:
    """Tests for FileService"""

    @pytest.mark.asyncio
    async def test_upload_file_success(self, test_db, test_user):
        """Test successful file upload with mocked MinIO"""
        from app.services.file_service import FileService

        # Mock MinIO client
        mock_storage = MagicMock()
        mock_storage.upload_bytes = AsyncMock()

        with patch("app.services.file_service.MinIOClient", return_value=mock_storage):
            service = FileService(test_db)

            file_content = b"fake video content" * 1000
            result = await service.upload_from_request(
                user_id=test_user.id,
                filename="test_video.mp4",
                content=file_content,
                content_type="video/mp4",
                metadata={"duration": 120, "resolution": "1920x1080"}
            )

            assert result is not None
            assert result.user_id == test_user.id
            assert result.original_filename == "test_video.mp4"
            assert result.size == len(file_content)
            assert result.content_type == "video/mp4"
            assert result.is_deleted is False

            # Verify MinIO upload was called
            mock_storage.upload_bytes.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_file_invalid_extension(self, test_db, test_user):
        """Test file upload with invalid extension raises ValueError"""
        from app.services.file_service import FileService

        service = FileService(test_db)

        with pytest.raises(ValueError, match="File validation failed"):
            await service.upload_from_request(
                user_id=test_user.id,
                filename="test_file.exe",
                content=b"content",
                content_type="application/x-msdownload"
            )

    @pytest.mark.asyncio
    async def test_upload_file_invalid_content_type(self, test_db, test_user):
        """Test file upload with invalid content type raises ValueError"""
        from app.services.file_service import FileService

        service = FileService(test_db)

        with pytest.raises(ValueError, match="File validation failed"):
            await service.upload_from_request(
                user_id=test_user.id,
                filename="test.pdf",
                content=b"content",
                content_type="application/pdf"
            )

    @pytest.mark.asyncio
    async def test_upload_file_too_large(self, test_db, test_user, monkeypatch):
        """Test file upload with too large file raises ValueError"""
        from app.services.file_service import FileService
        from app.config import get_settings

        # Mock max upload size to a small value
        settings = get_settings()
        original_max_size = settings.MAX_UPLOAD_SIZE

        monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE", 100)

        service = FileService(test_db)

        try:
            with pytest.raises(ValueError, match="File validation failed"):
                await service.upload_from_request(
                    user_id=test_user.id,
                    filename="test.mp4",
                    content=b"x" * 1000,
                    content_type="video/mp4"
                )
        finally:
            # Restore original setting
            monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE", original_max_size)

    @pytest.mark.asyncio
    async def test_get_file_info_success(self, test_db, test_file):
        """Test getting file info successfully"""
        from app.services.file_service import FileService

        service = FileService(test_db)
        result = await service.get_file_info(test_file.id, test_file.user_id)

        assert result is not None
        assert result.id == test_file.id
        assert result.original_filename == test_file.original_filename

    @pytest.mark.asyncio
    async def test_get_file_info_not_owner(self, test_db, test_file, sample_user):
        """Test getting file info by non-owner returns None"""
        from app.services.file_service import FileService

        # Create another user
        from app.database.models.user import User
        from app.auth.security import SecurityService

        security = SecurityService()
        other_user = User(
            username="otheruser",
            email="other@example.com",
            hashed_password=security.hash_password("TestPassword123"),
            is_admin=False,
            is_active=True
        )
        test_db.add(other_user)
        await test_db.commit()
        await test_db.refresh(other_user)

        service = FileService(test_db)
        result = await service.get_file_info(test_file.id, other_user.id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_file_info_deleted_file(self, test_db, test_file):
        """Test getting info of deleted file returns None"""
        from app.services.file_service import FileService

        # Mark file as deleted
        test_file.is_deleted = True
        await test_db.commit()

        service = FileService(test_db)
        result = await service.get_file_info(test_file.id, test_file.user_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_files_success(self, test_db, test_file):
        """Test getting user files successfully"""
        from app.services.file_service import FileService

        service = FileService(test_db)
        result = await service.get_user_files(test_file.user_id, offset=0, limit=10)

        assert isinstance(result, list)
        assert len(result) > 0
        assert any(f.id == test_file.id for f in result)

    @pytest.mark.asyncio
    async def test_get_user_files_pagination(self, test_db, test_file):
        """Test getting user files with pagination"""
        from app.services.file_service import FileService

        service = FileService(test_db)
        result = await service.get_user_files(test_file.user_id, offset=0, limit=5)

        assert isinstance(result, list)
        assert len(result) <= 5

    @pytest.mark.asyncio
    async def test_get_user_files_count(self, test_db, test_file):
        """Test getting user files count"""
        from app.services.file_service import FileService

        service = FileService(test_db)
        count = await service.get_user_files_count(test_file.user_id)

        assert isinstance(count, int)
        assert count >= 1

    @pytest.mark.asyncio
    async def test_delete_file_success(self, test_db, test_file):
        """Test successful file deletion"""
        from app.services.file_service import FileService

        # Mock MinIO client
        mock_storage = MagicMock()
        mock_storage.delete_file = AsyncMock()

        with patch("app.services.file_service.MinIOClient", return_value=mock_storage):
            service = FileService(test_db)
            result = await service.delete_file(test_file.id, test_file.user_id)

            assert result is True

            # Verify MinIO delete was called
            mock_storage.delete_file.assert_called_once()

            # Verify file is marked as deleted in database
            await test_db.refresh(test_file)
            assert test_file.is_deleted is True

    @pytest.mark.asyncio
    async def test_delete_file_not_owner(self, test_db, test_file, sample_user):
        """Test deleting file by non-owner returns False"""
        from app.services.file_service import FileService

        service = FileService(test_db)
        result = await service.delete_file(test_file.id, sample_user.id + 1)

        assert result is False

    @pytest.mark.asyncio
    async def test_download_file_success(self, test_db, test_file):
        """Test successful file download"""
        from app.services.file_service import FileService

        # Mock MinIO client
        mock_response = MagicMock()
        mock_response.read = MagicMock(return_value=b"file content")

        mock_storage = MagicMock()
        mock_storage.client = MagicMock()
        mock_storage.client.get_object = MagicMock(return_value=mock_response)

        with patch("app.services.file_service.MinIOClient", return_value=mock_storage):
            service = FileService(test_db)
            result = await service.download_file(test_file.id, test_file.user_id)

            assert result is not None
            assert isinstance(result, bytes)

    @pytest.mark.asyncio
    async def test_download_file_not_found(self, test_db, test_file):
        """Test downloading non-existent file returns None"""
        from app.services.file_service import FileService

        service = FileService(test_db)
        result = await service.download_file(99999, test_file.user_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_download_url(self, test_db, test_file):
        """Test getting download URL"""
        from app.services.file_service import FileService
        from datetime import timedelta

        mock_storage = MagicMock()
        mock_storage.get_file_url = AsyncMock(return_value="http://localhost:9000/bucket/file.mp4")

        with patch("app.services.file_service.MinIOClient", return_value=mock_storage):
            service = FileService(test_db)
            url = await service.get_download_url(test_file, expires=timedelta(hours=1))

            assert url == "http://localhost:9000/bucket/file.mp4"
            mock_storage.get_file_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_from_url_success(self, test_db, test_user):
        """Test uploading file from URL successfully"""
        from app.services.file_service import FileService

        # Mock httpx client
        mock_response = MagicMock()
        mock_response.content = b"remote file content" * 1000
        mock_response.headers = {"content-type": "video/mp4"}
        mock_response.raise_for_status = MagicMock()

        async def mock_get(*args, **kwargs):
            return mock_response

        async def mock_async_client(*args, **kwargs):
            client_mock = MagicMock()
            client_mock.get = mock_get
            client_mock.__aenter__ = AsyncMock(return_value=client_mock)
            client_mock.__aexit__ = AsyncMock()
            return client_mock

        # Mock MinIO
        mock_storage = MagicMock()
        mock_storage.upload_bytes = AsyncMock()

        with patch("app.services.file_service.httpx.AsyncClient", side_effect=mock_async_client):
            with patch("app.services.file_service.MinIOClient", return_value=mock_storage):
                service = FileService(test_db)
                result = await service.upload_from_url(
                    user_id=test_user.id,
                    url="http://example.com/video.mp4"
                )

                assert result is not None
                assert result.user_id == test_user.id
                assert result.content_type == "video/mp4"

    @pytest.mark.asyncio
    async def test_file_to_metadata(self, test_db):
        """Test _file_to_metadata static method"""
        from app.services.file_service import FileService

        # Test with valid metadata
        metadata = {
            "duration": 120.5,
            "width": 1920,
            "height": 1080,
            "video_codec": "h264",
            "audio_codec": "aac",
            "bitrate": 5000000
        }

        result = FileService._file_to_metadata(metadata)

        assert result is not None
        assert result.duration == 120.5
        assert result.width == 1920
        assert result.height == 1080
        assert result.video_codec == "h264"
        assert result.audio_codec == "aac"
        assert result.bitrate == 5000000

    @pytest.mark.asyncio
    async def test_file_to_metadata_none(self, test_db):
        """Test _file_to_metadata with None input"""
        from app.services.file_service import FileService

        result = FileService._file_to_metadata(None)

        assert result is None

    @pytest.mark.asyncio
    async def test_file_to_metadata_empty_dict(self, test_db):
        """Test _file_to_metadata with empty dict"""
        from app.services.file_service import FileService

        result = FileService._file_to_metadata({})

        assert result is not None
        assert result.duration is None
        assert result.width is None
        assert result.height is None

    @pytest.mark.asyncio
    async def test_storage_path_generation(self, test_db):
        """Test storage path generation"""
        from app.services.file_service import FileService

        service = FileService(test_db)
        path = service._storage_path(1, "test_video.mp4")

        assert path is not None
        assert path.startswith("1/")
        assert "test_video.mp4" in path
        assert len(path.split("/")[-1]) == 41  # UUID (32) + underscore (1) + filename (8)
