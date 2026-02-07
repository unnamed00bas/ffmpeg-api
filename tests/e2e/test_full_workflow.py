"""
End-to-end tests for complete user workflows
"""
import pytest
import asyncio
from httpx import AsyncClient
from datetime import datetime, timedelta


@pytest.mark.e2e
@pytest.mark.slow
class TestFullWorkflow:
    """End-to-end tests for complete user workflows"""

    @pytest.mark.asyncio
    async def test_complete_user_workflow(
        self,
        client: AsyncClient,
        temp_video_file: str
    ):
        """Test complete user workflow: register → login → upload → create task → check status"""

        # 1. Register new user
        register_response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "workflow_user",
                "email": "workflow@example.com",
                "password": "Workflow123"
            }
        )
        assert register_response.status_code == 201
        register_data = register_response.json()
        assert register_data["username"] == "workflow_user"

        # 2. Login
        login_response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "workflow@example.com",
                "password": "Workflow123"
            }
        )
        assert login_response.status_code == 200
        login_data = login_response.json()
        assert "access_token" in login_data
        token = login_data["access_token"]

        # 3. Upload file
        client.headers = {"Authorization": f"Bearer {token}"}

        with open(temp_video_file, "rb") as f:
            upload_response = await client.post(
                "/api/v1/files/upload",
                files={"file": ("workflow.mp4", f, "video/mp4")}
            )
        assert upload_response.status_code == 201
        upload_data = upload_response.json()
        file_id = upload_data["id"]

        # 4. Get user files to verify upload
        files_response = await client.get("/api/v1/files")
        assert files_response.status_code == 200
        files_data = files_response.json()
        assert len(files_data["files"]) >= 1

        # 5. Create text overlay task
        task_response = await client.post(
            "/api/v1/tasks/text-overlay",
            json={
                "video_file_id": file_id,
                "text": "Sample Watermark",
                "position": {"x": 100, "y": 100},
                "font_size": 24,
                "font_color": "#FFFFFF",
                "output_filename": "watermarked.mp4"
            }
        )
        assert task_response.status_code == 201
        task_data = task_response.json()
        task_id = task_data["id"]
        assert task_data["type"] == "text_overlay"
        assert task_data["status"] == "pending"

        # 6. Check task status (polling)
        max_retries = 30  # 30 seconds
        retry_count = 0
        final_status = None

        while retry_count < max_retries:
            await asyncio.sleep(1)

            status_response = await client.get(f"/api/v1/tasks/{task_id}")
            assert status_response.status_code == 200
            status_data = status_response.json()
            final_status = status_data["status"]

            if final_status in ["completed", "failed"]:
                break

            retry_count += 1

        assert final_status is not None
        assert final_status in ["completed", "failed", "processing", "pending"]

        # 7. Get task details
        final_status_response = await client.get(f"/api/v1/tasks/{task_id}")
        assert final_status_response.status_code == 200
        final_task_data = final_status_response.json()

        assert final_task_data["id"] == task_id
        assert "created_at" in final_task_data
        assert "updated_at" in final_task_data

        # 8. List user tasks
        tasks_response = await client.get("/api/v1/tasks")
        assert tasks_response.status_code == 200
        tasks_data = tasks_response.json()
        assert len(tasks_data["tasks"]) >= 1

        # 9. Get user profile
        me_response = await client.get("/api/v1/auth/me")
        assert me_response.status_code == 200
        me_data = me_response.json()
        assert me_data["username"] == "workflow_user"
        assert me_data["email"] == "workflow@example.com"

        # 10. Test refresh token
        refresh_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": login_data["refresh_token"]}
        )
        assert refresh_response.status_code == 200
        refresh_data = refresh_response.json()
        assert "access_token" in refresh_data
        assert "refresh_token" in refresh_data

    @pytest.mark.asyncio
    async def test_video_join_workflow(
        self,
        client: AsyncClient,
        temp_video_file: str
    ):
        """Test video joining workflow"""

        # 1. Login
        login_response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "test@example.com",
                "password": "TestPassword123"
            }
        )
        if login_response.status_code != 200:
            # Register user if not exists
            await client.post(
                "/api/v1/auth/register",
                json={
                    "username": "join_test",
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

        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        client.headers = {"Authorization": f"Bearer {token}"}

        # 2. Upload two files
        file_ids = []
        for i in range(2):
            with open(temp_video_file, "rb") as f:
                upload_response = await client.post(
                    "/api/v1/files/upload",
                    files={"file": (f"video{i}.mp4", f, "video/mp4")}
                )
            assert upload_response.status_code == 201
            file_ids.append(upload_response.json()["id"])

        # 3. Create join task
        join_response = await client.post(
            "/api/v1/tasks/join",
            json={
                "file_ids": file_ids,
                "output_filename": "joined.mp4"
            }
        )
        assert join_response.status_code == 201
        task_id = join_response.json()["id"]

        # 4. Monitor task progress
        for _ in range(20):
            await asyncio.sleep(1)
            status_response = await client.get(f"/api/v1/tasks/{task_id}")
            status_data = status_response.json()

            if status_data["status"] in ["completed", "failed"]:
                break

            # Check progress
            if status_data["progress"]:
                assert 0 <= status_data["progress"] <= 100

        # 5. Verify task exists in list
        tasks_response = await client.get("/api/v1/tasks?type=join")
        assert tasks_response.status_code == 200
        tasks_data = tasks_response.json()
        assert any(t["id"] == task_id for t in tasks_data["tasks"])

    @pytest.mark.asyncio
    async def test_task_cancellation_workflow(
        self,
        client: AsyncClient,
        temp_video_file: str
    ):
        """Test task cancellation workflow"""

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
                    "username": "cancel_test",
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

        # 3. Create long-running task (text overlay)
        task_response = await client.post(
            "/api/v1/tasks/text-overlay",
            json={
                "video_file_id": file_id,
                "text": "Cancel Test",
                "position": {"x": 50, "y": 50},
                "output_filename": "cancel_test.mp4"
            }
        )
        task_id = task_response.json()["id"]

        # 4. Cancel task
        cancel_response = await client.post(f"/api/v1/tasks/{task_id}/cancel")
        assert cancel_response.status_code == 200

        # 5. Verify task status
        status_response = await client.get(f"/api/v1/tasks/{task_id}")
        status_data = status_response.json()
        assert status_data["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_error_recovery_workflow(
        self,
        client: AsyncClient
    ):
        """Test error handling and recovery"""

        # 1. Test invalid credentials
        login_response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "wrong@example.com",
                "password": "wrongpassword"
            }
        )
        assert login_response.status_code == 401

        # 2. Test invalid token
        client.headers = {"Authorization": "Bearer invalid_token"}
        me_response = await client.get("/api/v1/auth/me")
        assert me_response.status_code == 401

        # 3. Test non-existent file
        client.headers = {}  # Remove invalid token
        file_response = await client.get("/api/v1/files/99999")
        assert file_response.status_code == 401  # Unauthorized

        # 4. Test non-existent task
        client.headers = {}
        task_response = await client.get("/api/v1/tasks/99999")
        assert task_response.status_code == 401  # Unauthorized

        # 5. Test validation errors
        register_response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "invalid user!",  # Invalid username
                "email": "invalid@example.com",
                "password": "weak"
            }
        )
        assert register_response.status_code == 422

    @pytest.mark.asyncio
    async def test_pagination_workflow(
        self,
        client: AsyncClient,
        temp_video_file: str
    ):
        """Test pagination workflow"""

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
                    "username": "pagination_test",
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

        # 2. Upload multiple files
        for i in range(15):
            with open(temp_video_file, "rb") as f:
                await client.post(
                    "/api/v1/files/upload",
                    files={"file": (f"file{i}.mp4", f, "video/mp4")}
                )

        # 3. Test pagination
        page1_response = await client.get("/api/v1/files?offset=0&limit=10")
        page1_data = page1_response.json()
        assert len(page1_data["files"]) == 10
        assert page1_data["page"] == 1
        assert page1_data["page_size"] == 10
        assert page1_data["total"] >= 15

        page2_response = await client.get("/api/v1/files?offset=10&limit=10")
        page2_data = page2_response.json()
        assert len(page2_data["files"]) >= 5
        assert page2_data["page"] == 2

        # 4. Test filters
        filtered_response = await client.get("/api/v1/files?offset=0&limit=5")
        filtered_data = filtered_response.json()
        assert len(filtered_data["files"]) <= 5
