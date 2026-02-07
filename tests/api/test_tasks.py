"""
Unit tests for tasks API endpoints: create_task, get_task, list_tasks, cancel, retry
"""
import pytest
from fastapi import status
from unittest.mock import MagicMock
from app.database.models.task import TaskType, TaskStatus


class TestCreateTask:
    """Tests for creating tasks"""

    @pytest.mark.asyncio
    async def test_create_join_task_success(self, authorized_client, test_file, test_db):
        """Test creating a join video task successfully"""
        # Create another test file
        from app.database.models.file import File
        from datetime import datetime

        file2 = File(
            user_id=test_file.user_id,
            filename="test_video2.mp4",
            original_filename="test_video2.mp4",
            size=1024000,
            content_type="video/mp4",
            storage_path="/test/path/test_video2.mp4",
            metadata={"duration": 120, "resolution": "1920x1080", "codec": "h264"},
            is_deleted=False,
            created_at=datetime.utcnow()
        )
        test_db.add(file2)
        await test_db.commit()
        await test_db.refresh(file2)

        response = await authorized_client.post(
            "/api/v1/tasks/join",
            json={
                "file_ids": [test_file.id, file2.id],
                "output_filename": "joined_video.mp4"
            }
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "id" in data
        assert data["type"] == TaskType.JOIN
        assert data["status"] == TaskStatus.PENDING
        assert data["config"]["output_filename"] == "joined_video.mp4"

    @pytest.mark.asyncio
    async def test_create_join_task_insufficient_files(self, authorized_client, test_file):
        """Test creating join task with less than 2 files returns 422"""
        response = await authorized_client.post(
            "/api/v1/tasks/join",
            json={
                "file_ids": [test_file.id],
                "output_filename": "joined_video.mp4"
            }
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "At least 2 files required" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_join_task_file_not_found(self, authorized_client):
        """Test creating join task with non-existent file returns 404"""
        response = await authorized_client.post(
            "/api/v1/tasks/join",
            json={
                "file_ids": [99999, 100000],
                "output_filename": "joined_video.mp4"
            }
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_create_task_unauthorized(self, client, test_file):
        """Test creating task without authentication returns 401"""
        response = await client.post(
            "/api/v1/tasks/join",
            json={
                "file_ids": [test_file.id, test_file.id + 1],
                "output_filename": "joined_video.mp4"
            }
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestGetTasks:
    """Tests for getting tasks"""

    @pytest.mark.asyncio
    async def test_list_tasks_success(self, authorized_client):
        """Test listing tasks successfully"""
        response = await authorized_client.get("/api/v1/tasks")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "tasks" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data

    @pytest.mark.asyncio
    async def test_list_tasks_with_filters(self, authorized_client):
        """Test listing tasks with status and type filters"""
        response = await authorized_client.get(
            "/api/v1/tasks?status=pending&type=join"
        )
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_list_tasks_with_pagination(self, authorized_client):
        """Test listing tasks with pagination"""
        response = await authorized_client.get(
            "/api/v1/tasks?offset=0&limit=10"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10

    @pytest.mark.asyncio
    async def test_list_tasks_unauthorized(self, client):
        """Test listing tasks without authentication returns 401"""
        response = await client.get("/api/v1/tasks")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_get_task_success(self, authorized_client, sample_task):
        """Test getting a specific task successfully"""
        response = await authorized_client.get(f"/api/v1/tasks/{sample_task.id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == sample_task.id
        assert data["type"] == sample_task.type
        assert data["status"] == sample_task.status

    @pytest.mark.asyncio
    async def test_get_task_not_found(self, authorized_client):
        """Test getting non-existent task returns 404"""
        response = await authorized_client.get("/api/v1/tasks/99999")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_task_unauthorized(self, client, sample_task):
        """Test getting task without authentication returns 401"""
        response = await client.get(f"/api/v1/tasks/{sample_task.id}")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestCancelTask:
    """Tests for canceling tasks"""

    @pytest.mark.asyncio
    async def test_cancel_task_success(self, authorized_client, test_db, sample_user):
        """Test canceling a pending task successfully"""
        from app.database.models.task import Task
        from datetime import datetime

        # Create a pending task
        task = Task(
            user_id=sample_user.id,
            type=TaskType.JOIN,
            status=TaskStatus.PENDING,
            input_files=[1, 2],
            output_files=[],
            config={"output_filename": "test.mp4"},
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

        response = await authorized_client.post(f"/api/v1/tasks/{task.id}/cancel")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == task.id
        assert data["status"] == TaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_task_not_found(self, authorized_client):
        """Test canceling non-existent task returns 404"""
        response = await authorized_client.post("/api/v1/tasks/99999/cancel")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_cancel_task_unauthorized(self, client, sample_task):
        """Test canceling task without authentication returns 401"""
        response = await client.post(f"/api/v1/tasks/{sample_task.id}/cancel")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestRetryTask:
    """Tests for retrying failed tasks"""

    @pytest.mark.asyncio
    async def test_retry_failed_task_success(self, authorized_client, test_db, sample_user):
        """Test retrying a failed task successfully"""
        from app.database.models.task import Task
        from datetime import datetime

        # Create a failed task
        task = Task(
            user_id=sample_user.id,
            type=TaskType.JOIN,
            status=TaskStatus.FAILED,
            input_files=[1, 2],
            output_files=[],
            config={"output_filename": "test.mp4"},
            error_message="Processing failed",
            progress=50.0,
            result=None,
            retry_count=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        test_db.add(task)
        await test_db.commit()
        await test_db.refresh(task)

        response = await authorized_client.post(f"/api/v1/tasks/{task.id}/retry")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == task.id
        assert data["status"] == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_retry_non_failed_task_returns_error(self, authorized_client, sample_task):
        """Test retrying a non-failed task returns 400"""
        response = await authorized_client.post(f"/api/v1/tasks/{sample_task.id}/retry")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Only failed tasks" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_retry_task_not_found(self, authorized_client):
        """Test retrying non-existent task returns 404"""
        response = await authorized_client.post("/api/v1/tasks/99999/retry")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestTextOverlayTask:
    """Tests for text overlay task creation"""

    @pytest.mark.asyncio
    async def test_create_text_overlay_task_success(self, authorized_client, test_file):
        """Test creating text overlay task successfully"""
        response = await authorized_client.post(
            "/api/v1/tasks/text-overlay",
            json={
                "video_file_id": test_file.id,
                "text": "Sample Text",
                "position": {"x": 100, "y": 100},
                "font_size": 24,
                "font_color": "#FFFFFF",
                "output_filename": "text_overlayed.mp4"
            }
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "id" in data
        assert data["type"] == TaskType.TEXT_OVERLAY

    @pytest.mark.asyncio
    async def test_create_text_overlay_task_file_not_found(self, authorized_client):
        """Test creating text overlay task with non-existent file returns 404"""
        response = await authorized_client.post(
            "/api/v1/tasks/text-overlay",
            json={
                "video_file_id": 99999,
                "text": "Sample Text",
                "position": {"x": 100, "y": 100}
            }
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestAudioOverlayTask:
    """Tests for audio overlay task creation"""

    @pytest.mark.asyncio
    async def test_create_audio_overlay_task_success(self, authorized_client, test_file, test_db):
        """Test creating audio overlay task successfully"""
        from app.database.models.file import File
        from datetime import datetime

        # Create audio file
        audio_file = File(
            user_id=test_file.user_id,
            filename="test_audio.mp3",
            original_filename="test_audio.mp3",
            size=512000,
            content_type="audio/mpeg",
            storage_path="/test/path/test_audio.mp3",
            metadata={"duration": 30, "codec": "mp3"},
            is_deleted=False,
            created_at=datetime.utcnow()
        )
        test_db.add(audio_file)
        await test_db.commit()
        await test_db.refresh(audio_file)

        response = await authorized_client.post(
            "/api/v1/tasks/audio-overlay",
            json={
                "video_file_id": test_file.id,
                "audio_file_id": audio_file.id,
                "audio_volume": 1.0,
                "output_filename": "audio_overlayed.mp4"
            }
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "id" in data
        assert data["type"] == TaskType.AUDIO_OVERLAY

    @pytest.mark.asyncio
    async def test_create_audio_overlay_task_video_not_found(self, authorized_client):
        """Test creating audio overlay task with non-existent video file returns 404"""
        response = await authorized_client.post(
            "/api/v1/tasks/audio-overlay",
            json={
                "video_file_id": 99999,
                "audio_file_id": 1,
                "audio_volume": 1.0
            }
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestVideoOverlayTask:
    """Tests for video overlay (picture-in-picture) task creation"""

    @pytest.mark.asyncio
    async def test_create_video_overlay_task_success(self, authorized_client, test_file, test_db):
        """Test creating video overlay task successfully"""
        from app.database.models.file import File
        from datetime import datetime

        # Create overlay video file
        overlay_file = File(
            user_id=test_file.user_id,
            filename="overlay_video.mp4",
            original_filename="overlay_video.mp4",
            size=512000,
            content_type="video/mp4",
            storage_path="/test/path/overlay_video.mp4",
            metadata={"duration": 30, "resolution": "640x480", "codec": "h264"},
            is_deleted=False,
            created_at=datetime.utcnow()
        )
        test_db.add(overlay_file)
        await test_db.commit()
        await test_db.refresh(overlay_file)

        response = await authorized_client.post(
            "/api/v1/tasks/video-overlay",
            json={
                "base_video_file_id": test_file.id,
                "overlay_video_file_id": overlay_file.id,
                "overlay_position": {"x": 10, "y": 10},
                "overlay_size": {"width": 200, "height": 150},
                "output_filename": "video_overlayed.mp4"
            }
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "id" in data
        assert data["type"] == TaskType.VIDEO_OVERLAY


class TestCombinedTask:
    """Tests for combined operations task creation"""

    @pytest.mark.asyncio
    async def test_create_combined_task_success(self, authorized_client, test_file):
        """Test creating combined operations task successfully"""
        response = await authorized_client.post(
            "/api/v1/tasks/combined",
            json={
                "base_file_id": test_file.id,
                "operations": [
                    {
                        "type": "text_overlay",
                        "params": {
                            "text": "First text",
                            "position": {"x": 100, "y": 100}
                        }
                    },
                    {
                        "type": "text_overlay",
                        "params": {
                            "text": "Second text",
                            "position": {"x": 200, "y": 200}
                        }
                    }
                ],
                "output_filename": "combined_output.mp4"
            }
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "id" in data
        assert data["type"] == TaskType.COMBINED

    @pytest.mark.asyncio
    async def test_create_combined_task_insufficient_operations(self, authorized_client, test_file):
        """Test creating combined task with less than 2 operations returns 422"""
        response = await authorized_client.post(
            "/api/v1/tasks/combined",
            json={
                "base_file_id": test_file.id,
                "operations": [
                    {
                        "type": "text_overlay",
                        "params": {"text": "Text"}
                    }
                ]
            }
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "At least 2 operations" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_combined_task_too_many_operations(self, authorized_client, test_file):
        """Test creating combined task with more than 10 operations returns 422"""
        operations = [
            {
                "type": "text_overlay",
                "params": {"text": f"Text {i}", "position": {"x": i*10, "y": i*10}}
            }
            for i in range(11)
        ]

        response = await authorized_client.post(
            "/api/v1/tasks/combined",
            json={
                "base_file_id": test_file.id,
                "operations": operations
            }
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "Maximum 10 operations" in response.json()["detail"]
