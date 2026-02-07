"""
API endpoints тесты для /admin/*: tasks, users, metrics, queue, cleanup.
"""
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock

from app.main import app


class TestAdminEndpoints:
    """Тесты админских endpoints."""

    @pytest.mark.asyncio
    async def test_get_all_tasks_filters_by_status_and_user(self):
        """GET /admin/tasks возвращает задачи с фильтрами."""
        mock_db = MagicMock()
        with patch("app.api.v1.admin.get_current_admin_user") as mock_admin:
            mock_admin.return_value = MagicMock()
            with patch("app.api.v1.admin.get_db", return_value=mock_db):
                task_repo_mock = MagicMock()
                task_repo_mock.get_all_tasks = AsyncMock(
                    return_value=MagicMock(tasks=[], total=0)
                )
                from app.database.models.task import TaskStatus
                with patch("app.api.v1.admin.TaskRepository", return_value=task_repo_mock):
                    async with AsyncClient(app=app, base_url="http://test") as ac:
                        resp = await ac.get(
                            "/api/v1/admin/tasks?status=processing&user_id=5&offset=0&limit=20"
                        )
            assert resp.status_code == 200
            task_repo_mock.get_all_tasks.assert_called_once_with(
                status=TaskStatus.PROCESSING,
                user_id=5,
                offset=0,
                limit=20,
            )

    @pytest.mark.asyncio
    async def test_get_all_tasks_invalid_status_422(self):
        """GET /admin/tasks с невалидным статусом возвращает 422."""
        with patch("app.api.v1.admin.get_current_admin_user") as mock_admin:
            mock_admin.return_value = MagicMock()
            async with AsyncClient(app=app, base_url="http://test") as ac:
                resp = await ac.get("/api/v1/admin/tasks?status=invalid")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_get_all_users_with_task_counts(self):
        """GET /admin/users возвращает пользователей со счётчиком задач."""
        mock_db = MagicMock()
        with patch("app.api.v1.admin.get_current_admin_user") as mock_admin:
            mock_admin.return_value = MagicMock()
            with patch("app.api.v1.admin.get_db", return_value=mock_db):
                user_repo_mock = MagicMock()
                user_repo_mock.get_users = AsyncMock(return_value=[
                    MagicMock(id=1, username="alice", email="a@e.com"),
                    MagicMock(id=2, username="bob", email="b@e.com"),
                ])
                user_repo_mock.count = AsyncMock(return_value=2)
                task_repo_mock = MagicMock()
                task_repo_mock.get_tasks_statistics = AsyncMock(side_effect=[{"total": 5}, {"total": 3}])
                with patch("app.api.v1.admin.UserRepository", return_value=user_repo_mock):
                    with patch("app.api.v1.admin.TaskRepository", return_value=task_repo_mock):
                        async with AsyncClient(app=app, base_url="http://test") as ac:
                            resp = await ac.get("/api/v1/admin/users?offset=0&limit=20")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 2
            assert len(data["users"]) == 2
            assert data["users"][0]["tasks_count"] == 5
            assert data["users"][1]["tasks_count"] == 3

    @pytest.mark.asyncio
    async def test_get_metrics_returns_system_stats(self):
        """GET /admin/metrics возвращает системные метрики."""
        mock_db = MagicMock()
        with patch("app.api.v1.admin.get_current_admin_user") as mock_admin:
            mock_admin.return_value = MagicMock()
            with patch("app.api.v1.admin.get_db", return_value=mock_db):
                task_repo_mock = MagicMock()
                task_repo_mock.get_all_tasks_statistics = AsyncMock(
                    return_value={
                        "total": 100,
                        "by_status": {"completed": 80, "failed": 10, "processing": 10},
                    }
                )
                file_repo_mock = MagicMock()
                file_repo_mock.get_total_storage_usage = AsyncMock(return_value=1073741824)  # 1 GB
                file_repo_mock.count_all = AsyncMock(return_value=50)
                user_repo_mock = MagicMock()
                user_repo_mock.count = AsyncMock(return_value=10)
                with patch("app.api.v1.admin.TaskRepository", return_value=task_repo_mock):
                    with patch("app.api.v1.admin.FileRepository", return_value=file_repo_mock):
                        with patch("app.api.v1.admin.UserRepository", return_value=user_repo_mock):
                            async with AsyncClient(app=app, base_url="http://test") as ac:
                                resp = await ac.get("/api/v1/admin/metrics")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_users"] == 10
            assert data["total_tasks"] == 100
            assert data["completed_tasks"] == 80
            assert data["failed_tasks"] == 10
            assert data["processing_tasks"] == 10
            assert data["total_files"] == 50
            assert data["total_storage"] == 1073741824
            assert "queue_size" in data
            assert "active_workers" in data

    @pytest.mark.asyncio
    async def test_get_queue_status_returns_counts(self):
        """GET /admin/queue-status возвращает статусы очереди."""
        with patch("app.api.v1.admin.get_current_admin_user") as mock_admin:
            mock_admin.return_value = MagicMock()
            with patch("app.api.v1.admin.celery_app") as mock_celery:
                inspect_mock = MagicMock()
                inspect_mock.active.return_value = {
                    "worker1": [{"id": "t1"}],
                    "worker2": [{"id": "t2"}],
                }
                inspect_mock.scheduled.return_value = {"worker1": []}
                inspect_mock.reserved.return_value = {}
                mock_celery_app.control.inspect.return_value = inspect_mock
                async with AsyncClient(app=app, base_url="http://test") as ac:
                    resp = await ac.get("/api/v1/admin/queue-status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["processing"] == 2
            assert data["pending"] == 0
            assert data["reserved"] == 0
            assert data["total"] == 2
            assert "worker1" in data["workers"]
            assert "worker2" in data["workers"]

    @pytest.mark.asyncio
    async def test_manual_cleanup_invokes_tasks(self):
        """POST /admin/cleanup запускает очистку с параметрами."""
        with patch("app.api.v1.admin.get_current_admin_user") as mock_admin:
            mock_admin.return_value = MagicMock()
            with patch(
                "app.api.v1.admin._async_cleanup_old_files"
            ) as cleanup_files_mock, \
                 patch("app.api.v1.admin._async_cleanup_temp_files", return_value=5), \
                 patch("app.api.v1.admin._async_cleanup_old_tasks", return_value=12) as cleanup_tasks_mock:
                cleanup_files_mock.return_value = "Deleted 10 old files"
                async with AsyncClient(app=app, base_url="http://test") as ac:
                    resp = await ac.post(
                        "/api/v1/admin/cleanup?file_retention_days=30&task_retention_days=90"
                    )
            assert resp.status_code == 200
            data = resp.json()
            assert "Deleted 10 old files" in data.get("files", "")
            assert "Deleted 12 old tasks" in data.get("tasks", "")
            assert "Deleted 5 temp files" in data.get("temp_files", "")

    @pytest.mark.asyncio
    async def test_non_admin_forbidden(self):
        """Невалидный админ-токен возвращает 403."""
        mock_db = MagicMock()
        with patch("app.api.v1.admin.get_db", return_value=mock_db):
            with patch("app.api.v1.admin.get_current_admin_user") as mock_admin:
                from fastapi import HTTPException
                mock_admin.side_effect = HTTPException(status_code=403, detail="Not enough permissions")
                async with AsyncClient(app=app, base_url="http://test") as ac:
                    resp = await ac.get("/api/v1/admin/metrics")
            assert resp.status_code == 403
