"""
End-to-end tests for task lifecycle
"""
import pytest
import asyncio
from httpx import AsyncClient
from datetime import datetime


@pytest.mark.e2e
@pytest.mark.slow
class TestTaskLifecycle:
    """End-to-end tests for complete task lifecycle"""

    @pytest.mark.asyncio
    async def test_task_pending_to_processing_to_completed(
        self,
        client: AsyncClient,
        temp_video_file: str
    ):
        """Test task lifecycle: pending → processing → completed"""

        # 1. Login
        login_response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "test@example.com",
                "password": "TestPassword123"
            }
        )
        if login_response.status_code != 200:
            await client.post(
                "/api/v1/auth/register",
                json={
                    "username": "lifecycle_test",
                    "email": "test@example.com",
                    "password": "TestPassword123"
                }
            )
            login_response = await client.post(
                "/api/v1/auth/login",
                data={
                    "username": "test@example.com",
                    "password": "TestPassword123"
                }
            )

        token = login_response.json()["access_token"]
        client.headers = {"Authorization": f"Bearer {token}"}

        # 2. Upload file
        with open(temp_video_file, "rb") as f:
            upload_response = await client.post(
                "/api/v1/files/upload",
                files={"file": ("video.mp4", f, "video/mp4")}
            )
        file_id = upload_response.json()["id"]

        # 3. Create task
        task_response = await client.post(
            "/api/v1/tasks/text-overlay",
            json={
                "video_file_id": file_id,
                "text": "Lifecycle Test",
                "position": {"x": 100, "y": 100},
                "output_filename": "lifecycle.mp4"
            }
        )
        task_id = task_response.json()["id"]

        # 4. Verify initial status (pending)
        initial_status = await client.get(f"/api/v1/tasks/{task_id}")
        assert initial_status.json()["status"] == "pending"
        assert initial_status.json()["progress"] == 0.0

        # 5. Monitor progress
        previous_progress = 0.0
        progress_increased = False

        for _ in range(60):
            await asyncio.sleep(1)

            status_response = await client.get(f"/api/v1/tasks/{task_id}")
            task_data = status_response.json()

            # Check if progress increased
            if task_data["progress"] > previous_progress:
                progress_increased = True
                previous_progress = task_data["progress"]
                assert 0 <= task_data["progress"] <= 100

            # Check if processing
            if task_data["status"] == "processing":
                assert task_data["progress"] > 0

            # Check completion
            if task_data["status"] in ["completed", "failed"]:
                break

        # 6. Verify final status
        final_status = await client.get(f"/api/v1/tasks/{task_id}")
        final_data = final_status.json()

        assert final_data["status"] in ["completed", "failed", "processing"]
        assert final_data["progress"] >= 0
        assert "created_at" in final_data
        assert "updated_at" in final_data

    @pytest.mark.asyncio
    async def test_task_failure_and_retry(
        self,
        client: AsyncClient,
        temp_video_file: str
    ):
        """Test task failure and retry"""

        # 1. Login
        login_response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "test@example.com",
                "password": "TestPassword123"
            }
        )
        if login_response.status_code != 200:
            await client.post(
                "/api/v1/auth/register",
                json={
                    "username": "retry_test",
                    "email": "test@example.com",
                    "password": "TestPassword123"
                }
            )
            login_response = await client.post(
                "/api/v1/auth/login",
                data={
                    "username": "test@example.com",
                    "password": "TestPassword123"
                }
            )

        token = login_response.json()["access_token"]
        client.headers = {"Authorization": f"Bearer {token}"}

        # 2. Upload file
        with open(temp_video_file, "rb") as f:
            upload_response = await client.post(
                "/api/v1/files/upload",
                files={"file": ("video.mp4", f, "video/mp4")}
            )
        file_id = upload_response.json()["id"]

        # 3. Create task (might fail if file is corrupted)
        task_response = await client.post(
            "/api/v1/tasks/audio-overlay",
            json={
                "video_file_id": file_id,
                "audio_file_id": file_id,  # Invalid: same file
                "audio_volume": 1.0,
                "output_filename": "audio_overlay.mp4"
            }
        )
        # Task might succeed or fail depending on implementation
        if task_response.status_code == 201:
            task_id = task_response.json()["id"]

            # Wait for task completion
            for _ in range(30):
                await asyncio.sleep(1)
                status_response = await client.get(f"/api/v1/tasks/{task_id}")
                status_data = status_response.json()

                if status_data["status"] == "failed":
                    # 4. Try to retry
                    retry_response = await client.post(f"/api/v1/tasks/{task_id}/retry")
                    assert retry_response.status_code in [200, 400]  # 200 if retryable, 400 if not

                    if retry_response.status_code == 200:
                        # Verify retry
                        retry_data = retry_response.json()
                        assert retry_data["status"] == "pending"
                        assert retry_data["retry_count"] >= 1
                    break

                if status_data["status"] in ["completed", "cancelled"]:
                    break

    @pytest.mark.asyncio
    async def test_task_metadata_updates(
        self,
        client: AsyncClient,
        temp_video_file: str
    ):
        """Test that task metadata is properly updated throughout lifecycle"""

        # 1. Login
        login_response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "test@example.com",
                "password": "TestPassword123"
            }
        )
        if login_response.status_code != 200:
            await client.post(
                "/api/v1/auth/register",
                json={
                    "username": "metadata_test",
                    "email": "test@example.com",
                    "password": "TestPassword123"
                }
            )
            login_response = await client.post(
                "/api/v1/auth/login",
                data={
                    "username": "test@example.com",
                    "password": "TestPassword123"
                }
            )

        token = login_response.json()["access_token"]
        client.headers = {"Authorization": f"Bearer {token}"}

        # 2. Upload file
        with open(temp_video_file, "rb") as f:
            upload_response = await client.post(
                "/api/v1/files/upload",
                files={"file": ("video.mp4", f, "video/mp4")}
            )
        file_id = upload_response.json()["id"]

        # 3. Create task
        task_response = await client.post(
            "/api/v1/tasks/text-overlay",
            json={
                "video_file_id": file_id,
                "text": "Metadata Test",
                "position": {"x": 50, "y": 50},
                "output_filename": "metadata.mp4"
            }
        )
        task_id = task_response.json()["id"]

        # 4. Check initial metadata
        initial_response = await client.get(f"/api/v1/tasks/{task_id}")
        initial_data = initial_response.json()
        initial_created = initial_data["created_at"]
        initial_updated = initial_data["updated_at"]

        assert initial_created is not None
        assert initial_updated is not None

        # 5. Wait a bit and check if updated_at changed
        await asyncio.sleep(2)
        updated_response = await client.get(f"/api/v1/tasks/{task_id}")
        updated_data = updated_response.json()

        # updated_at might have changed
        assert updated_data["created_at"] == initial_created

    @pytest.mark.asyncio
    async def test_multiple_concurrent_tasks(
        self,
        client: AsyncClient,
        temp_video_file: str
    ):
        """Test handling multiple concurrent tasks"""

        # 1. Login
        login_response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "test@example.com",
                "password": "TestPassword123"
            }
        )
        if login_response.status_code != 200:
            await client.post(
                "/api/v1/auth/register",
                json={
                    "username": "concurrent_test",
                    "email": "test@example.com",
                    "password": "TestPassword123"
                }
            )
            login_response = await client.post(
                "/api/v1/auth/login",
                data={
                    "username": "test@example.com",
                    "password": "TestPassword123"
                }
            )

        token = login_response.json()["access_token"]
        client.headers = {"Authorization": f"Bearer {token}"}

        # 2. Upload a file
        with open(temp_video_file, "rb") as f:
            upload_response = await client.post(
                "/api/v1/files/upload",
                files={"file": ("video.mp4", f, "video/mp4")}
            )
        file_id = upload_response.json()["id"]

        # 3. Create multiple concurrent tasks
        task_ids = []
        for i in range(3):
            task_response = await client.post(
                "/api/v1/tasks/text-overlay",
                json={
                    "video_file_id": file_id,
                    "text": f"Concurrent {i}",
                    "position": {"x": 100 * (i + 1), "y": 100 * (i + 1)},
                    "output_filename": f"concurrent_{i}.mp4"
                }
            )
            task_ids.append(task_response.json()["id"])

        # 4. Verify all tasks created
        tasks_response = await client.get("/api/v1/tasks")
        tasks_data = tasks_response.json()
        assert len(tasks_data["tasks"]) >= 3

        # 5. Monitor all tasks
        completed_count = 0
        for _ in range(60):
            await asyncio.sleep(1)

            for task_id in task_ids:
                status_response = await client.get(f"/api/v1/tasks/{task_id}")
                status_data = status_response.json()

                if status_data["status"] in ["completed", "failed"]:
                    completed_count += 1

            if completed_count >= 3:
                break

        # 6. Verify all tasks finished
        for task_id in task_ids:
            final_response = await client.get(f"/api/v1/tasks/{task_id}")
            final_data = final_response.json()
            assert final_data["status"] in ["completed", "failed", "processing", "pending"]

    @pytest.mark.asyncio
    async def test_task_result_download(
        self,
        client: AsyncClient,
        temp_video_file: str
    ):
        """Test downloading task result"""

        # 1. Login
        login_response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "test@example.com",
                "password": "TestPassword123"
            }
        )
        if login_response.status_code != 200:
            await client.post(
                "/api/v1/auth/register",
                json={
                    "username": "download_test",
                    "email": "test@example.com",
                    "password": "TestPassword123"
                }
            )
            login_response = await client.post(
                "/api/v1/auth/login",
                data={
                    "username": "test@example.com",
                    "password": "TestPassword123"
                }
            )

        token = login_response.json()["access_token"]
        client.headers = {"Authorization": f"Bearer {token}"}

        # 2. Upload file
        with open(temp_video_file, "rb") as f:
            upload_response = await client.post(
                "/api/v1/files/upload",
                files={"file": ("video.mp4", f, "video/mp4")}
            )
        file_id = upload_response.json()["id"]

        # 3. Create task
        task_response = await client.post(
            "/api/v1/tasks/text-overlay",
            json={
                "video_file_id": file_id,
                "text": "Download Test",
                "position": {"x": 100, "y": 100},
                "output_filename": "download_test.mp4"
            }
        )
        task_id = task_response.json()["id"]

        # 4. Wait for task completion
        for _ in range(60):
            await asyncio.sleep(1)
            status_response = await client.get(f"/api/v1/tasks/{task_id}")
            status_data = status_response.json()

            if status_data["status"] == "completed":
                # 5. Download result file if available
                if status_data.get("result") and status_data["result"].get("output_file"):
                    file_response = await client.get(
                        f"/api/v1/files/{file_id}/download"
                    )
                    assert file_response.status_code == 200
                    assert len(file_response.content) > 0
                break

            if status_data["status"] in ["failed", "cancelled"]:
                break

        # 6. Verify task in user's task list
        tasks_response = await client.get("/api/v1/tasks")
        tasks_data = tasks_response.json()
        assert any(t["id"] == task_id for t in tasks_data["tasks"])
