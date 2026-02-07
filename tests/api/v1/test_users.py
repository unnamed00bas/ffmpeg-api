"""
API endpoints тесты для /users/*: /me, settings, stats, history.
"""
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestUsersEndpoints:
    """Тесты пользователей."""

    @pytest.mark.asyncio
    async def test_get_me_returns_user_info(self):
        """GET /users/me возвращает данные текущего пользователя."""
        with patch("app.api.v1.users.get_current_active_user") as mock_user:
            mock_user.return_value = MagicMock(
                id=1,
                username="testuser",
                email="test@example.com",
                is_admin=False,
                is_active=True,
                settings={"theme": "dark"},
                created_at="2025-01-01",
                updated_at="2025-01-01",
            )
            async with AsyncClient(app=app, base_url="http://test") as ac:
                resp = await ac.get("/api/v1/users/me")
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == 1
            assert data["username"] == "testuser"
            assert data["email"] == "test@example.com"
            assert data["is_admin"] is False
            assert data["settings"] == {"theme": "dark"}

    @pytest.mark.asyncio
    async def test_get_settings_returns_settings(self):
        """GET /users/me/settings возвращает настройки."""
        with patch("app.api.v1.users.get_current_active_user") as mock_user:
            mock_user.return_value = MagicMock(
                settings={"language": "ru"},
                created_at="2025-01-01",
                updated_at="2025-01-01",
            )
            async with AsyncClient(app=app, base_url="http://test") as ac:
                resp = await ac.get("/api/v1/users/me/settings")
            assert resp.status_code == 200
            data = resp.json()
            assert data["settings"] == {"language": "ru"}

    @pytest.mark.asyncio
    async def test_put_settings_merges_with_existing(self):
        """PUT /users/me/settings объединяет настройки."""
        mock_db = MagicMock()
        with patch("app.api.v1.users.get_current_active_user") as mock_user:
            mock_user.return_value = MagicMock(id=1, settings={"old": "value"})
            with patch("app.api.v1.users.get_db", return_value=mock_db):
                repo_mock = MagicMock()
                repo_mock.update_by_id = AsyncMock()
                repo_mock.get_by_id = AsyncMock(return_value=MagicMock(settings={"old": "value", "new": "key"}))
                with patch("app.api.v1.users.UserRepository", return_value=repo_mock):
                    async with AsyncClient(app=app, base_url="http://test") as ac:
                        resp = await ac.put("/api/v1/users/me/settings", json={"new": "key"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["settings"]["old"] == "value"
            assert data["settings"]["new"] == "key"

    @pytest.mark.asyncio
    async def test_get_stats_returns_task_and_storage_stats(self):
        """GET /users/me/stats возвращает статистику."""
        mock_db = MagicMock()
        with patch("app.api.v1.users.get_current_active_user") as mock_user:
            mock_user.return_value = MagicMock(id=1)
            with patch("app.api.v1.users.get_db", return_value=mock_db):
                task_repo_mock = MagicMock()
                task_repo_mock.get_tasks_statistics = AsyncMock(return_value={
                    "total": 10,
                    "by_status": {"completed": 8, "failed": 1, "processing": 1},
                })
                file_repo_mock = MagicMock()
                file_repo_mock.get_user_storage_usage = AsyncMock(return_value=52428800)  # 50 MB
                file_repo_mock.get_user_file_count = AsyncMock(return_value=5)
                with patch("app.api.v1.users.TaskRepository", return_value=task_repo_mock):
                    with patch("app.api.v1.users.FileRepository", return_value=file_repo_mock):
                        async with AsyncClient(app=app, base_url="http://test") as ac:
                            resp = await ac.get("/api/v1/users/me/stats")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total_tasks"] == 10
            assert data["completed_tasks"] == 8
            assert data["failed_tasks"] == 1
            assert data["processing_tasks"] == 1
            assert data["total_files"] == 5
            assert data["storage_used"] == 52428800
            assert data["storage_limit"] == 1073741824

    @pytest.mark.asyncio
    async def test_get_history_filters_by_status(self):
        """GET /users/me/history фильтрует по статусу."""
        mock_db = MagicMock()
        with patch("app.api.v1.users.get_current_active_user") as mock_user:
            mock_user.return_value = MagicMock(id=1)
            with patch("app.api.v1.users.get_db", return_value=mock_db):
                task_repo_mock = MagicMock()
                task_repo_mock.get_by_user = AsyncMock(return_value=[MagicMock(id=1), MagicMock(id=2)])
                task_repo_mock.count_by_user = AsyncMock(return_value=2)
                from app.database.models.task import TaskStatus
                with patch("app.api.v1.users.TaskRepository", return_value=task_repo_mock):
                    async with AsyncClient(app=app, base_url="http://test") as ac:
                        resp = await ac.get("/api/v1/users/me/history?status=completed&limit=20&offset=0")
            assert resp.status_code == 200
            task_repo_mock.get_by_user.assert_called_once_with(
                1, offset=0, limit=20, filters={"status": TaskStatus.COMPLETED}
            )

    @pytest.mark.asyncio
    async def test_get_history_invalid_status_422(self):
        """GET /users/me/history с невалидным статусом возвращает 422."""
        mock_db = MagicMock()
        with patch("app.api.v1.users.get_current_active_user") as mock_user:
            mock_user.return_value = MagicMock(id=1)
            with patch("app.api.v1.users.get_db", return_value=mock_db):
                async with AsyncClient(app=app, base_url="http://test") as ac:
                    resp = await ac.get("/api/v1/users/me/history?status=invalid")
            assert resp.status_code == 422
            assert "detail" in resp.json()
