"""
Unit tests for files API endpoints: upload, get_files, delete_file
"""
import pytest
from fastapi import status
from unittest.mock import MagicMock


class TestFileUpload:
    """Tests for file upload endpoint"""

    @pytest.mark.asyncio
    async def test_upload_file_success(self, authorized_client):
        """Test successful file upload"""
        # Create test video content
        file_content = b"fake video content" * 1000

        response = await authorized_client.post(
            "/api/v1/files/upload",
            files={
                "file": ("test_video.mp4", file_content, "video/mp4")
            }
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "id" in data
        assert data["filename"] is not None
        assert data["original_filename"] == "test_video.mp4"
        assert data["size"] == len(file_content)
        assert data["content_type"] == "video/mp4"
        assert "download_url" in data

    @pytest.mark.asyncio
    async def test_upload_file_unauthorized(self, client):
        """Test file upload without authentication returns 401"""
        file_content = b"fake video content" * 1000

        response = await client.post(
            "/api/v1/files/upload",
            files={
                "file": ("test_video.mp4", file_content, "video/mp4")
            }
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_upload_file_no_filename(self, authorized_client):
        """Test file upload without filename returns 422"""
        response = await authorized_client.post(
            "/api/v1/files/upload",
            files={
                "file": (None, b"content", "video/mp4")
            }
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_upload_file_from_url_success(self, authorized_client, monkeypatch):
        """Test file upload from URL"""
        from unittest.mock import AsyncMock, patch

        # Mock httpx client
        mock_response = MagicMock()
        mock_response.content = b"fake video content" * 1000
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

        with patch("app.services.file_service.httpx.AsyncClient", side_effect=mock_async_client):
            response = await authorized_client.post(
                "/api/v1/files/upload-url",
                json={"url": "http://example.com/video.mp4"}
            )
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert "id" in data
            assert "download_url" in data


class TestGetFiles:
    """Tests for getting files endpoint"""

    @pytest.mark.asyncio
    async def test_get_files_success(self, authorized_client, test_file):
        """Test getting list of files"""
        response = await authorized_client.get("/api/v1/files")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "files" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert len(data["files"]) > 0

    @pytest.mark.asyncio
    async def test_get_files_with_pagination(self, authorized_client):
        """Test getting files with pagination"""
        response = await authorized_client.get("/api/v1/files?offset=0&limit=10")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10

    @pytest.mark.asyncio
    async def test_get_files_unauthorized(self, client):
        """Test getting files without authentication returns 401"""
        response = await client.get("/api/v1/files")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_get_file_info_success(self, authorized_client, test_file):
        """Test getting specific file info"""
        response = await authorized_client.get(f"/api/v1/files/{test_file.id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == test_file.id
        assert data["original_filename"] == test_file.original_filename
        assert data["size"] == test_file.size

    @pytest.mark.asyncio
    async def test_get_file_info_not_found(self, authorized_client):
        """Test getting non-existent file returns 404"""
        response = await authorized_client.get("/api/v1/files/99999")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_file_info_unauthorized(self, client, test_file):
        """Test getting file info without authentication returns 401"""
        response = await client.get(f"/api/v1/files/{test_file.id}")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_download_file_success(self, authorized_client, test_file):
        """Test downloading a file"""
        response = await authorized_client.get(f"/api/v1/files/{test_file.id}/download")
        assert response.status_code == status.HTTP_200_OK
        assert response.content is not None

    @pytest.mark.asyncio
    async def test_download_file_not_found(self, authorized_client):
        """Test downloading non-existent file returns 404"""
        response = await authorized_client.get("/api/v1/files/99999/download")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestDeleteFile:
    """Tests for file deletion endpoint"""

    @pytest.mark.asyncio
    async def test_delete_file_success(self, authorized_client, test_db, test_user):
        """Test successful file deletion"""
        from app.database.models.file import File
        from datetime import datetime

        # Create a test file
        file = File(
            user_id=test_user.id,
            filename="delete_test.mp4",
            original_filename="delete_test.mp4",
            size=1024,
            content_type="video/mp4",
            storage_path="/test/delete_test.mp4",
            metadata={},
            is_deleted=False,
            created_at=datetime.utcnow()
        )
        test_db.add(file)
        await test_db.commit()
        await test_db.refresh(file)

        # Delete the file
        response = await authorized_client.delete(f"/api/v1/files/{file.id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

    @pytest.mark.asyncio
    async def test_delete_file_not_found(self, authorized_client):
        """Test deleting non-existent file returns 404"""
        response = await authorized_client.delete("/api/v1/files/99999")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_file_unauthorized(self, client, test_file):
        """Test deleting file without authentication returns 401"""
        response = await client.delete(f"/api/v1/files/{test_file.id}")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestChunkedUpload:
    """Tests for chunked file upload endpoint"""

    @pytest.mark.asyncio
    async def test_initiate_chunk_upload_success(self, authorized_client):
        """Test initiating chunked upload"""
        response = await authorized_client.post(
            "/api/v1/files/upload-init",
            data={
                "filename": "large_video.mp4",
                "total_size": 104857600,  # 100 MB
                "total_chunks": 10,
                "content_type": "video/mp4"
            }
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "upload_id" in data

    @pytest.mark.asyncio
    async def test_upload_chunk_success(self, authorized_client):
        """Test uploading a chunk"""
        # First initiate upload
        init_response = await authorized_client.post(
            "/api/v1/files/upload-init",
            data={
                "filename": "large_video.mp4",
                "total_size": 104857600,
                "total_chunks": 10,
                "content_type": "video/mp4"
            }
        )
        upload_id = init_response.json()["upload_id"]

        # Upload chunk
        chunk_data = b"chunk content" * 1000
        response = await authorized_client.post(
            f"/api/v1/files/upload-chunk/{upload_id}/0",
            files={"chunk_data": ("chunk0", chunk_data, "application/octet-stream")}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "uploaded"
        assert data["chunk_number"] == 0

    @pytest.mark.asyncio
    async def test_complete_upload_success(self, authorized_client):
        """Test completing chunked upload"""
        from unittest.mock import AsyncMock, patch

        # Mock the complete_upload method
        with patch("app.services.chunk_upload.ChunkUploadManager.complete_upload") as mock_complete:
            mock_complete.return_value = AsyncMock(
                return_value=MagicMock(
                    id=1,
                    user_id=1,
                    filename="large_video.mp4",
                    original_filename="large_video.mp4",
                    size=104857600,
                    content_type="video/mp4",
                    file_metadata={},
                    created_at="2025-01-01T00:00:00"
                )
            )

            response = await authorized_client.post(
                "/api/v1/files/upload-complete/test-upload-id",
                data={"output_filename": "final_video.mp4"}
            )
            assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_abort_upload_success(self, authorized_client):
        """Test aborting chunked upload"""
        # First initiate upload
        init_response = await authorized_client.post(
            "/api/v1/files/upload-init",
            data={
                "filename": "large_video.mp4",
                "total_size": 104857600,
                "total_chunks": 10,
                "content_type": "video/mp4"
            }
        )
        upload_id = init_response.json()["upload_id"]

        # Abort upload
        response = await authorized_client.post(f"/api/v1/files/upload-abort/{upload_id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "aborted"
