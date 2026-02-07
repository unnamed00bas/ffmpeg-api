"""
Unit tests for admin API endpoints: tasks, users, metrics, queue-status, cleanup
"""
import pytest
from fastapi import status
from unittest.mock import MagicMock, AsyncMock


class TestAdminTasks:
    """Tests for admin tasks endpoint"""

    @pytest.mark.asyncio
    async def test_get_all_tasks_as_admin(self, admin_client):
        """Test getting all tasks as admin"""
        response = await admin_client.get("/api/v1/admin/tasks")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "tasks" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data

    @pytest.mark.asyncio
    async def test_get_all_tasks_with_status_filter(self, admin_client):
        """Test getting all tasks with status filter"""
        response = await admin_client.get("/api/v1/admin/tasks?status=pending")
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_get_all_tasks_with_user_filter(self, admin_client):
        """Test getting all tasks with user_id filter"""
        response = await admin_client.get("/api/v1/admin/tasks?user_id=1")
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_get_all_tasks_with_pagination(self, admin_client):
        """Test getting all tasks with pagination"""
        response = await admin_client.get("/api/v1/admin/tasks?offset=0&limit=10")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10

    @pytest.mark.asyncio
    async def test_get_all_tasks_invalid_status(self, admin_client):
        """Test getting all tasks with invalid status returns 422"""
        response = await admin_client.get("/api/v1/admin/tasks?status=invalid")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "Invalid status" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_all_tasks_unauthorized(self, authorized_client):
        """Test getting all tasks as regular user returns 403"""
        response = await authorized_client.get("/api/v1/admin/tasks")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_get_all_tasks_without_auth(self, client):
        """Test getting all tasks without authentication returns 401"""
        response = await client.get("/api/v1/admin/tasks")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestAdminUsers:
    """Tests for admin users endpoint"""

    @pytest.mark.asyncio
    async def test_get_all_users_as_admin(self, admin_client):
        """Test getting all users as admin"""
        response = await admin_client.get("/api/v1/admin/users")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "users" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert len(data["users"]) > 0

    @pytest.mark.asyncio
    async def test_get_all_users_with_pagination(self, admin_client):
        """Test getting all users with pagination"""
        response = await admin_client.get("/api/v1/admin/users?offset=0&limit=10")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10

    @pytest.mark.asyncio
    async def test_get_all_users_unauthorized(self, authorized_client):
        """Test getting all users as regular user returns 403"""
        response = await authorized_client.get("/api/v1/admin/users")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_get_all_users_without_auth(self, client):
        """Test getting all users without authentication returns 401"""
        response = await client.get("/api/v1/admin/users")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestAdminMetrics:
    """Tests for admin metrics endpoint"""

    @pytest.mark.asyncio
    async def test_get_system_metrics_as_admin(self, admin_client):
        """Test getting system metrics as admin"""
        response = await admin_client.get("/api/v1/admin/metrics")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "total_users" in data
        assert "total_tasks" in data
        assert "completed_tasks" in data
        assert "failed_tasks" in data
        assert "processing_tasks" in data
        assert "total_files" in data
        assert "total_storage" in data
        assert "queue_size" in data
        assert "active_workers" in data

    @pytest.mark.asyncio
    async def test_get_system_metrics_unauthorized(self, authorized_client):
        """Test getting system metrics as regular user returns 403"""
        response = await authorized_client.get("/api/v1/admin/metrics")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_get_system_metrics_without_auth(self, client):
        """Test getting system metrics without authentication returns 401"""
        response = await client.get("/api/v1/admin/metrics")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestAdminQueueStatus:
    """Tests for admin queue status endpoint"""

    @pytest.mark.asyncio
    async def test_get_queue_status_as_admin(self, admin_client):
        """Test getting queue status as admin"""
        response = await admin_client.get("/api/v1/admin/queue-status")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "pending" in data
        assert "processing" in data
        assert "reserved" in data
        assert "total" in data
        assert "workers" in data
        assert isinstance(data["workers"], list)

    @pytest.mark.asyncio
    async def test_get_queue_status_unauthorized(self, authorized_client):
        """Test getting queue status as regular user returns 403"""
        response = await authorized_client.get("/api/v1/admin/queue-status")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_get_queue_status_without_auth(self, client):
        """Test getting queue status without authentication returns 401"""
        response = await client.get("/api/v1/admin/queue-status")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestAdminCleanup:
    """Tests for admin cleanup endpoint"""

    @pytest.mark.asyncio
    async def test_manual_cleanup_files_as_admin(self, admin_client):
        """Test manual cleanup of old files as admin"""
        response = await admin_client.post(
            "/api/v1/admin/cleanup",
            params={"file_retention_days": 30}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "files" in data or "temp_files" in data

    @pytest.mark.asyncio
    async def test_manual_cleanup_tasks_as_admin(self, admin_client):
        """Test manual cleanup of old tasks as admin"""
        response = await admin_client.post(
            "/api/v1/admin/cleanup",
            params={"task_retention_days": 90}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "tasks" in data or "temp_files" in data

    @pytest.mark.asyncio
    async def test_manual_cleanup_all_as_admin(self, admin_client):
        """Test manual cleanup of both files and tasks as admin"""
        response = await admin_client.post(
            "/api/v1/admin/cleanup",
            params={
                "file_retention_days": 30,
                "task_retention_days": 90
            }
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_manual_cleanup_invalid_retention_days(self, admin_client):
        """Test manual cleanup with invalid retention days returns 422"""
        response = await admin_client.post(
            "/api/v1/admin/cleanup",
            params={"file_retention_days": 0}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_manual_cleanup_unauthorized(self, authorized_client):
        """Test manual cleanup as regular user returns 403"""
        response = await authorized_client.post(
            "/api/v1/admin/cleanup",
            params={"file_retention_days": 30}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_manual_cleanup_without_auth(self, client):
        """Test manual cleanup without authentication returns 401"""
        response = await client.post(
            "/api/v1/admin/cleanup",
            params={"file_retention_days": 30}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestAdminAuthorization:
    """Tests for admin authorization"""

    @pytest.mark.asyncio
    async def test_regular_user_cannot_access_admin_endpoints(self, authorized_client):
        """Test that regular user cannot access any admin endpoints"""
        endpoints = [
            "/api/v1/admin/tasks",
            "/api/v1/admin/users",
            "/api/v1/admin/metrics",
            "/api/v1/admin/queue-status"
        ]

        for endpoint in endpoints:
            response = await authorized_client.get(endpoint)
            assert response.status_code == status.HTTP_403_FORBIDDEN, f"Failed for {endpoint}"

    @pytest.mark.asyncio
    async def test_unauthenticated_user_cannot_access_admin_endpoints(self, client):
        """Test that unauthenticated user cannot access any admin endpoints"""
        endpoints = [
            "/api/v1/admin/tasks",
            "/api/v1/admin/users",
            "/api/v1/admin/metrics",
            "/api/v1/admin/queue-status"
        ]

        for endpoint in endpoints:
            response = await client.get(endpoint)
            assert response.status_code == status.HTTP_401_UNAUTHORIZED, f"Failed for {endpoint}"
